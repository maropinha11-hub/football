#pragma once
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

/* Original fields at bone +0x80..+0xCC, in that exact order. */
typedef struct PesBoneTrack {
    float rotation_a[4], rotation_b[4];
    float translation_a[4], translation_b[4];
    float rotation_duration, rotation_elapsed;
    float translation_duration, translation_elapsed;
} PesBoneTrack;

typedef struct PesAnimationChannels {
    float clamped_time;
    uint32_t interval_index, channel_count, reserved;
    PesBoneTrack bones[19];
} PesAnimationChannels;

typedef struct PesLocalBonePose {
    float rotation[4], translation[4];
} PesLocalBonePose;

typedef struct PesLocalPose { PesLocalBonePose bones[19]; } PesLocalPose;

/* Decode SLES_519.12 format 0x20000002 with 19 linked bones, root first.
 * block is a single original motion data block (not an AFS or ELF).
 * Initialize inout from the original skeleton/previous channel state first:
 * non-root translations, translation W lanes and non-root elapsed values
 * retain the original no-write behavior. No resampling or normalization.
 * 1 success; 0 invalid; -1 unsupported format. Failures leave inout intact. */
int32_t pes_animation_channels_decode(const uint8_t *block, uint32_t size,
    float time, PesAnimationChannels *inout);

/* Recovered pose evaluation for that same format. Uses the original ordered
 * dot product, original shortest-arc test and original sin/atan polynomials,
 * with host binary32 and separate products/additions. This is not a hardware
 * parity certificate or the full animation/action/game loop. Output atomic. */
int32_t pes_animation_pose_evaluate(const PesAnimationChannels *channels,
    PesLocalPose *out);

#ifdef __cplusplus
}
#endif
