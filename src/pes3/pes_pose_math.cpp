#include "pes_pose_math_internal.h"
#include <stdint.h>
#include <string.h>

namespace {
float num(uint32_t b) { float f; memcpy(&f, &b, 4); return f; }
uint32_t raw(float f) { uint32_t b; memcpy(&b, &f, 4); return b; }

/* 010A74F0, restricted to finite nonnegative arguments. Each statement is
 * one original scalar operation; constants are the checked ELF data bits. */
float original_atan(float argument) {
    uint32_t magnitude = raw(argument);
    float x = argument;
    int region = -1;
    if (magnitude > 0x507FFFFFu) return num(0x3FC90FDAu) + num(0x33A22168u);
    if (magnitude > 0x3EDFFFFFu) {
        if (magnitude <= 0x3F97FFFFu) {
            if (magnitude <= 0x3F2FFFFFu) {
                float numerator = x + x;
                float denominator = x + 2.0f;
                numerator = numerator - 1.0f;
                x = numerator / denominator;
                region = 0;
            } else {
                float denominator = x + 1.0f;
                float numerator = x - 1.0f;
                x = numerator / denominator;
                region = 1;
            }
        } else if (magnitude <= 0x401BFFFFu) {
            float denominator = x * 1.5f;
            float numerator = x - 1.5f;
            denominator = denominator + 1.0f;
            x = numerator / denominator;
            region = 2;
        } else {
            x = -1.0f / x;
            region = 3;
        }
    } else if (magnitude <= 0x30FFFFFFu) {
        float huge = x + num(0x7149F2C9u);
        if (1.0f < huge) return x;
    }
    const uint32_t coefficient[11] = {0x3EAAAAABu,0xBE4CCCCCu,0x3E124924u,
        0xBDE38E38u,0x3DBA2E6Eu,0xBD9D8795u,0x3D886B34u,0xBD6EF16Au,
        0x3D4BDA59u,0xBD15A221u,0x3C8569D7u};
    float z = x * x;
    float w = z * z;
    float even = w * num(coefficient[10]);
    even = num(coefficient[8]) + even;
    float odd = w * num(coefficient[9]);
    odd = num(coefficient[7]) + odd;
    even = w * even;
    odd = w * odd;
    even = num(coefficient[6]) + even;
    odd = num(coefficient[5]) + odd;
    even = w * even;
    odd = w * odd;
    even = num(coefficient[4]) + even;
    odd = num(coefficient[3]) + odd;
    even = w * even;
    odd = w * odd;
    even = num(coefficient[2]) + even;
    odd = num(coefficient[1]) + odd;
    even = w * even;
    odd = w * odd;
    even = num(coefficient[0]) + even;
    even = z * even;
    float sum = even + odd;
    float correction = x * sum;
    if (region < 0) return x - correction;
    const uint32_t high[4] = {0x3EED6338u,0x3F490FDAu,0x3F7B985Du,0x3FC90FDAu};
    const uint32_t low[4] = {0x31AC3769u,0x33222167u,0x33140FB4u,0x33A22168u};
    correction = correction - num(low[region]);
    correction = correction - x;
    return num(high[region]) - correction;
}

/* 010A6A48. Small-angle kernel with its original tail correction. */
float kernel_sine(float x, float tail, bool corrected) {
    if ((raw(x) & 0x7FFFFFFFu) <= 0x31FFFFFFu) return x;
    float z = x * x;
    float r = z * num(0x2F2EC9D2u);
    float v = z * x;
    r = r + num(0xB2D72F34u);
    r = z * r;
    r = r + num(0x3638EF1Au);
    r = z * r;
    r = r + num(0xB9500D01u);
    r = z * r;
    r = r + num(0x3C088889u);
    if (!corrected) {
        r = z * r;
        r = r + num(0xBE2AAAAAu);
        r = v * r;
        return x + r;
    }
    float first = v * r;
    float second = v * num(0xBE2AAAAAu);
    r = tail * 0.5f;
    r = r - first;
    r = z * r;
    r = r - tail;
    r = r - second;
    return x - r;
}

/* 010A6090, input |x| <= pi/4 and the original reduction tail. */
float kernel_cosine(float x, float tail) {
    uint32_t magnitude = raw(x) & 0x7FFFFFFFu;
    if (magnitude <= 0x31FFFFFFu) return 1.0f;
    float z = x * x;
    float r = z * num(0xAD47D74Eu);
    r = r + num(0x310F74F5u);
    r = z * r;
    r = r + num(0xB493F27Bu);
    r = z * r;
    r = r + num(0x37D00D00u);
    r = z * r;
    r = r + num(0xBAB60B60u);
    r = z * r;
    r = r + num(0x3D2AAAAAu);
    r = z * r;
    float product = x * tail;
    if (magnitude <= 0x3E999999u) {
        r = z * r;
        float half = z * 0.5f;
        r = r - product;
        half = half - r;
        return 1.0f - half;
    }
    float q = num(0x3E900000u);
    if (magnitude <= 0x3F480000u) q = num(magnitude - 0x01000000u);
    r = z * r;
    float a = 1.0f - q;
    r = r - product;
    float half = z * 0.5f;
    half = half - q;
    half = half - r;
    return a - half;
}
} // namespace

float pes_pose_vu_round(float f) {
    uint32_t b = raw(f);
    if (!(b & 0x7F800000u)) return num(b & 0x80000000u);
    return f;
}

float pes_pose_original_angle(float sine, float cosine) {
    /* Reached 010A5580 positive quadrant. */
    if (raw(cosine) == 0x3F800000u) return original_atan(sine);
    if ((raw(sine) & 0x7FFFFFFFu) <= 0x007FFFFFu) return sine;
    if ((raw(cosine) & 0x7FFFFFFFu) <= 0x007FFFFFu) return num(0x3FC90FDAu);
    int32_t difference = static_cast<int32_t>(raw(sine) - raw(cosine));
    int32_t exponent_difference = difference >> 23;
    if (exponent_difference >= 61) return num(0x3FC90FDAu);
    float ratio = sine / cosine;
    return original_atan(ratio);
}

float pes_pose_original_sine(float angle) {
    /* Slerp supplies a nonnegative angle <= pi/2. 010A7AF0 therefore reaches
     * only the direct sine kernel or quadrant-one cosine after 010A5C10. */
    uint32_t magnitude = raw(angle) & 0x7FFFFFFFu;
    if (magnitude <= 0x3F490FD8u) return kernel_sine(angle, 0.0f, false);
    float reduced = angle - num(0x3FC90F80u);
    float remainder, tail;
    if ((magnitude & 0xFFFFFFF0u) != 0x3FC90FD0u) {
        tail = num(0x37354442u);
        remainder = reduced - tail;
    } else {
        reduced = reduced - num(0x373543FFu);
        tail = num(0x2E85A308u);
        remainder = reduced - tail;
    }
    float error = reduced - remainder;
    error = error - tail;
    return kernel_cosine(remainder, error);
}
