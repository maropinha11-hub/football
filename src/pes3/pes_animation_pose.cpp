#include "pes_animation_pose.h"
#include "pes_pose_math_internal.h"
#include <cmath>
#include <cstring>
#include <limits>

static_assert(sizeof(PesBoneTrack) == 80, "PES channel ABI");
static_assert(sizeof(PesAnimationChannels) == 1536, "PES channels ABI");
static_assert(sizeof(PesLocalPose) == 608, "PES pose ABI");
static_assert(sizeof(float) == 4 && std::numeric_limits<float>::is_iec559, "binary32 required");

namespace {
uint32_t word(const uint8_t *p) {
    return uint32_t(p[0]) | uint32_t(p[1]) << 8 | uint32_t(p[2]) << 16 | uint32_t(p[3]) << 24;
}
float number(uint32_t bits) { float f; std::memcpy(&f, &bits, 4); return f; }
float load_float(const uint8_t *p) { return number(word(p)); }
int32_t short_value(const uint8_t *p) {
    int32_t u = uint32_t(p[0]) | uint32_t(p[1]) << 8;
    return u < 32768 ? u : u - 65536;
}
void rotation(const uint8_t *p, float *out) {
    float scale = number(0x38000100u);
    for (uint32_t i = 0; i < 4; ++i) out[i] = pes_pose_vu_round(float(short_value(p + 2*i)) * scale);
}
float key_time(const uint8_t *table, uint32_t index) { return load_float(table + 4 + index*8); }
uint32_t key_offset(const uint8_t *table, uint32_t index) { return word(table + 8 + index*8); }
uint32_t select_interval(const uint8_t *table, uint32_t count, float time) {
    if (count < 2) return 0;
    if (count < 6) {
        uint32_t index = 0;
        while (index < count-2 && key_time(table,index) < time) ++index;
        return index;
    }
    uint32_t start = 0, length = count-1;
    while (length) {
        uint32_t middle = length/2;
        float candidate = key_time(table,start+middle);
        if (time == candidate) return start+middle;
        if (time < candidate) length = middle;
        else { length -= middle+1; start += middle+1; }
    }
    float candidate = key_time(table,start);
    if (candidate == 0.0f) return start-1;
    if (candidate < time) ++start;
    return start;
}
float vmul(float a, float b) {
    return pes_pose_vu_round(pes_pose_vu_round(a) * pes_pose_vu_round(b));
}
float vadd(float a, float b) {
    return pes_pose_vu_round(pes_pose_vu_round(a) + pes_pose_vu_round(b));
}
bool valid_track(const PesBoneTrack &b) {
    const float *groups[] = {b.rotation_a,b.rotation_b,b.translation_a,b.translation_b};
    for (const float *g : groups) for (uint32_t i=0;i<4;++i)
        if (!std::isfinite(g[i])) return false;
    if (!std::isfinite(b.rotation_duration) || !std::isfinite(b.rotation_elapsed)
        || !std::isfinite(b.translation_duration) || !std::isfinite(b.translation_elapsed)) return false;
    return b.rotation_duration >= 0.0f && b.rotation_elapsed >= 0.0f
        && b.translation_duration >= 0.0f && b.translation_elapsed >= 0.0f;
}
}

extern "C" int32_t pes_animation_channels_decode(const uint8_t *block, uint32_t size,
    float time, PesAnimationChannels *inout) {
    if (!block || !inout || size < 32 || !std::isfinite(time)) return 0;
    if (word(block) != 0x20011119u) return 0;
    if (word(block+4) != 0x20000002u) return -1;
    if (word(block+12) != 60) return -1;
    float duration = load_float(block+8);
    uint32_t table_offset = word(block+16);
    if (!(duration > 0.0f && duration <= 4096.0f) || table_offset > size-4) return 0;
    const uint8_t *table = block+table_offset;
    uint32_t count = word(table);
    if (!count || count > 512 || table_offset != 28+164*count
        || uint64_t(table_offset)+4+uint64_t(count)*8 > size) return 0;
    float previous = 0.0f;
    for (uint32_t i=0; i<count; ++i) {
        float current = key_time(table,i);
        if (key_offset(table,i) != 28+164*i) return -1;
        if (i == count-1) { if (current != 0.0f) return 0; }
        else {
            if (!std::isfinite(current) || !(current > previous) || current > duration) return 0;
            previous = current;
        }
    }
    float clamped = time;
    if (clamped < 0.0f) clamped = 0.0f;
    else if (!(clamped <= duration)) clamped = duration;
    uint32_t interval = select_interval(table,count,clamped);
    if (interval >= count || (count > 1 && interval >= count-1)) return 0;
    float start = interval ? key_time(table,interval-1) : 0.0f;
    float elapsed = clamped-start;
    float span = key_time(table,interval)-start;
    const uint8_t *a = block+key_offset(table,interval);
    const uint8_t *b = span == 0.0f ? a : block+key_offset(table,interval+1);
    PesAnimationChannels result = *inout;
    result.clamped_time = clamped;
    result.interval_index = interval;
    result.channel_count = 19;
    for (uint32_t i=0; i<19; ++i) {
        PesBoneTrack &bone = result.bones[i];
        rotation(a,bone.rotation_a); rotation(b,bone.rotation_b);
        bone.rotation_duration = span; bone.rotation_elapsed = elapsed;
        a+=8; b+=8;
        if (!i) {
            for (uint32_t j=0;j<3;++j) {
                bone.translation_a[j] = load_float(a+4*j);
                bone.translation_b[j] = load_float(b+4*j);
                if (!std::isfinite(bone.translation_a[j]) || !std::isfinite(bone.translation_b[j])) return 0;
            }
            bone.translation_duration = span; bone.translation_elapsed = elapsed;
            a+=12; b+=12;
        } else bone.translation_duration = 0.0f;
    }
    *inout = result;
    return 1;
}

extern "C" int32_t pes_animation_pose_evaluate(const PesAnimationChannels *channels, PesLocalPose *out) {
    if (!channels || !out || channels->channel_count != 19) return 0;
    PesLocalPose result;
    for (uint32_t i=0;i<19;++i) {
        const PesBoneTrack &b = channels->bones[i];
        if (!valid_track(b)) return 0;
        if (b.rotation_duration <= 0.0f) std::memcpy(result.bones[i].rotation,b.rotation_a,16);
        else {
            float alpha = 1.0f;
            if (b.rotation_elapsed < b.rotation_duration) alpha = b.rotation_elapsed/b.rotation_duration;
            float product[4];
            for (uint32_t j=0;j<4;++j) product[j] = vmul(b.rotation_a[j],b.rotation_b[j]);
            float dot = vadd(product[3],product[0]);
            dot = vadd(dot,product[1]); dot = vadd(dot,product[2]);
            bool flip = dot < 0.0f;
            if (flip) dot = -dot;
            float complement = 1.0f-dot;
            float weight_a, weight_b;
            if (complement <= number(0x3727C5ACu)) { weight_b=alpha; weight_a=1.0f-alpha; }
            else {
                float square = dot*dot;
                float remainder = 1.0f-square;
                if (!(remainder > 0.0f)) return 0;
                float sine = std::sqrt(remainder);
                float angle = pes_pose_original_angle(sine,dot);
                float reciprocal = 1.0f/sine;
                float argument_a = (1.0f-alpha)*angle;
                float original_a = pes_pose_original_sine(argument_a);
                weight_a = reciprocal*original_a;
                float argument_b = alpha*angle;
                float original_b = pes_pose_original_sine(argument_b);
                weight_b = reciprocal*original_b;
            }
            if (flip) weight_b=-weight_b;
            for (uint32_t j=0;j<4;++j) result.bones[i].rotation[j] =
                vadd(vmul(b.rotation_a[j],weight_a),vmul(b.rotation_b[j],weight_b));
        }
        if (i)
            std::memcpy(result.bones[i].translation,b.translation_a,16);
        else {
            float alpha=1.0f;
            if (b.translation_elapsed < b.translation_duration) alpha=b.translation_elapsed/b.translation_duration;
            float complement=pes_pose_vu_round(1.0f-pes_pose_vu_round(alpha));
            for (uint32_t j=0;j<4;++j) result.bones[i].translation[j] =
                vadd(vmul(b.translation_b[j],alpha),vmul(b.translation_a[j],complement));
        }
        for (uint32_t j=0;j<4;++j) if (!std::isfinite(result.bones[i].rotation[j])
            || !std::isfinite(result.bones[i].translation[j])) return 0;
    }
    *out=result;
    return 1;
}
