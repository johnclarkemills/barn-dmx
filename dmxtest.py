import time
import random
import math
from stupidArtnet.StupidArtnet import StupidArtnet

# --- USER CONFIG ---
TARGET_IP = '10.0.1.95'
UNIVERSE_COUNT = 4
COMPONENTS_PER_LED = 6
LED_COUNT_PER_STRIP = 18
LED_STRIPS_PER_UNIVERSE = 3
PACKET_SIZE = COMPONENTS_PER_LED * LED_COUNT_PER_STRIP * LED_STRIPS_PER_UNIVERSE

# Brightness (0.0 to 1.0)
BRIGHTNESS = 0.25

# Effect timing
EFFECT_DURATION = 15.0  # seconds per effect
CROSSFADE_DURATION = 3.0  # seconds to crossfade between effects
# --- END USER CONFIG ---

# Create StupidArtnet instances for each universe
universes = []
for u in range(UNIVERSE_COUNT):
    artnet = StupidArtnet(TARGET_IP, u, PACKET_SIZE)
    artnet.start()
    universes.append(artnet)
print(f"Sending Art-Net to {TARGET_IP} Universes 0-{UNIVERSE_COUNT - 1}...")

# --- COLOR UTILITIES ---
# RGBWAUV channel indices
CH_R, CH_G, CH_B, CH_W, CH_A, CH_UV = 0, 1, 2, 3, 4, 5

def make_color(color, brightness=None):
    """Create a 6-byte RGBWAUV color from a list/tuple of 6 values."""
    if brightness is None:
        brightness = BRIGHTNESS
    b = bytearray(6)
    for i, v in enumerate(color):
        b[i] = int(max(0, min(255, v * brightness)))
    return b

def blend_frames(frame1, frame2, t):
    """Blend two frames together. t=0 means frame1, t=1 means frame2."""
    result = bytearray(len(frame1))
    for i in range(len(frame1)):
        result[i] = int(lerp(frame1[i], frame2[i], t))
    return result

def lerp(a, b, t):
    """Linear interpolation between a and b by factor t (0.0 to 1.0)."""
    return a + (b - a) * t

def lerp_color(color1, color2, t):
    """Interpolate between two 6-channel colors."""
    return [lerp(color1[i], color2[i], t) for i in range(6)]

def smoothstep(t):
    """Smooth interpolation curve."""
    return t * t * (3 - 2 * t)

def noise1d(x):
    """Simple 1D noise using sine waves at different frequencies."""
    return (
        math.sin(x * 1.0) * 0.5 +
        math.sin(x * 2.3 + 1.3) * 0.25 +
        math.sin(x * 4.1 + 2.7) * 0.125 +
        math.sin(x * 8.7 + 0.5) * 0.0625
    ) / 0.9375  # Normalize to roughly -1 to 1

def flame_noise(led_index, t, speed=3.0, flicker=2.0):
    """Generate smooth flame-like noise value (0.0 to 1.0) for a specific LED."""
    # Each LED has a unique phase based on its index
    phase = led_index * 0.7
    # Combine slow movement with faster flicker
    slow = noise1d(t * speed * 0.3 + phase)
    fast = noise1d(t * speed * flicker + phase * 1.3 + 100)
    # Mix slow and fast, bias toward brighter values
    value = (slow * 0.6 + fast * 0.4 + 1.0) / 2.0
    # Add intensity variation per LED
    intensity_offset = noise1d(led_index * 0.5 + t * 0.5) * 0.2
    value = max(0.0, min(1.0, value + intensity_offset))
    return value

def gradient_color(gradient_stops, progress):
    """
    Get interpolated color from gradient stops at given progress (0.0 to 1.0).
    gradient_stops: list of [R, G, B, W, A, UV] colors
    """
    if progress <= 0:
        return gradient_stops[0]
    if progress >= 1:
        return gradient_stops[-1]

    num_segments = len(gradient_stops) - 1
    segment_progress = progress * num_segments
    segment_index = int(segment_progress)
    segment_t = segment_progress - segment_index

    if segment_index >= num_segments:
        segment_index = num_segments - 1
        segment_t = 1.0

    return lerp_color(gradient_stops[segment_index], gradient_stops[segment_index + 1], segment_t)


# --- EFFECT DEFINITIONS ---

def effect_noise(led_index, t, speed=1.0, scale=0.7):
    """Generic smooth noise for effects."""
    phase = led_index * scale
    value = (noise1d(t * speed + phase) + 1.0) / 2.0
    return max(0.0, min(1.0, value))


# 1. FLAME - warm flickering fire
FLAME_COLORS = [
    [40, 0, 0, 0, 0, 0],
    [255, 0, 0, 0, 80, 0],
    [255, 30, 0, 0, 200, 0],
    [200, 80, 0, 0, 255, 0],
    [150, 120, 0, 0, 255, 0],
]

def generate_flame(total_leds, t):
    result = bytearray()
    for i in range(total_leds):
        intensity = flame_noise(i, t, speed=3.0, flicker=2.0)
        color = gradient_color(FLAME_COLORS, intensity)
        result += make_color(color)
    return result


# 2. OCEAN - deep blue waves
OCEAN_COLORS = [
    [0, 0, 40, 0, 0, 30],      # Deep blue + hint UV
    [0, 20, 100, 0, 0, 60],    # Mid blue
    [0, 60, 180, 0, 0, 40],    # Brighter blue-teal
    [0, 100, 200, 40, 0, 20],  # Light blue + white hint
    [0, 60, 150, 0, 0, 50],    # Back to mid
]

def generate_ocean(total_leds, t):
    result = bytearray()
    for i in range(total_leds):
        # Slow rolling waves
        wave = (math.sin(t * 0.5 + i * 0.3) + 1) / 2
        ripple = (noise1d(t * 1.5 + i * 0.5) + 1) / 2
        intensity = wave * 0.7 + ripple * 0.3
        color = gradient_color(OCEAN_COLORS, intensity)
        result += make_color(color)
    return result


# 3. AURORA - northern lights
AURORA_COLORS = [
    [0, 80, 40, 0, 0, 60],     # Teal + UV
    [0, 200, 100, 0, 0, 100],  # Green + UV
    [40, 150, 200, 0, 0, 150], # Cyan + UV
    [100, 50, 200, 0, 0, 200], # Purple + UV
    [0, 180, 80, 0, 0, 80],    # Back to green
]

def generate_aurora(total_leds, t):
    result = bytearray()
    for i in range(total_leds):
        # Flowing curtain effect
        flow = (math.sin(t * 0.3 + i * 0.15) + 1) / 2
        shimmer = (noise1d(t * 2.0 + i * 0.8) + 1) / 2
        intensity = flow * 0.6 + shimmer * 0.4
        # Add some brightness variation
        brightness_mod = 0.5 + shimmer * 0.5
        color = gradient_color(AURORA_COLORS, intensity)
        color = [c * brightness_mod for c in color]
        result += make_color(color)
    return result


# 4. BREATHING - slow hypnotic pulse
BREATHING_COLORS = [
    [20, 0, 30, 0, 0, 40],     # Dark purple
    [60, 0, 100, 0, 20, 80],   # Purple + amber hint
    [100, 0, 150, 20, 40, 120],# Brighter purple
    [60, 0, 100, 0, 20, 80],   # Back down
]

def generate_breathing(total_leds, t):
    result = bytearray()
    # Global breathing cycle
    breath = (math.sin(t * 0.4) + 1) / 2
    breath = smoothstep(breath)  # Smoother curve

    for i in range(total_leds):
        # Slight variation per LED
        offset = noise1d(i * 0.3) * 0.15
        intensity = max(0, min(1, breath + offset))
        color = gradient_color(BREATHING_COLORS, intensity)
        result += make_color(color)
    return result


# 5. THUNDERSTORM - dark moody with occasional flashes
STORM_COLORS = [
    [0, 0, 20, 0, 0, 10],      # Very dark blue
    [0, 0, 40, 0, 0, 20],      # Dark blue
    [0, 0, 60, 10, 0, 30],     # Slightly brighter
]

def generate_thunderstorm(total_leds, t):
    result = bytearray()

    # Background rumble
    for i in range(total_leds):
        rumble = (noise1d(t * 0.8 + i * 0.4) + 1) / 2
        intensity = rumble * 0.5
        color = gradient_color(STORM_COLORS, intensity)

        # Random lightning flashes
        flash_chance = noise1d(t * 15 + i * 0.1)
        if flash_chance > 0.97:
            # Bright white flash
            flash_intensity = (flash_chance - 0.97) / 0.03
            color = lerp_color(color, [200, 200, 255, 255, 100, 150], flash_intensity)

        result += make_color(color)
    return result


# 6. LAVA - slow moving deep reds
LAVA_COLORS = [
    [30, 0, 0, 0, 0, 0],       # Dark red
    [100, 0, 0, 0, 30, 0],     # Red + amber hint
    [180, 20, 0, 0, 80, 0],    # Bright red-orange
    [255, 60, 0, 0, 150, 0],   # Hot orange
    [200, 30, 0, 0, 100, 0],   # Back to red
]

def generate_lava(total_leds, t):
    result = bytearray()
    for i in range(total_leds):
        # Very slow flow
        flow = (math.sin(t * 0.2 + i * 0.25) + 1) / 2
        bubble = (noise1d(t * 0.8 + i * 0.6) + 1) / 2
        intensity = flow * 0.5 + bubble * 0.5
        color = gradient_color(LAVA_COLORS, intensity)
        result += make_color(color)
    return result


# Effect registry
EFFECTS = [
    ("Flame", generate_flame),
    ("Ocean", generate_ocean),
    ("Aurora", generate_aurora),
    ("Breathing", generate_breathing),
    ("Thunderstorm", generate_thunderstorm),
    ("Lava", generate_lava),
]


# --- SCENE DEFINITIONS ---
class Scene:
    def __init__(self, name, gradient, duration, loop=True):
        self.name = name
        self.gradient = gradient
        self.duration = duration
        self.loop = loop

    def get_color(self, progress):
        return gradient_color(self.gradient, progress)


SCENES = {
    "all_components": Scene(
        name="All Components",
        gradient=[
            [255, 0, 0, 0, 0, 0],    # Red
            [0, 255, 0, 0, 0, 0],    # Green
            [0, 0, 255, 0, 0, 0],    # Blue
            [0, 0, 0, 255, 0, 0],    # White
            [0, 0, 0, 0, 255, 0],    # Amber
            [0, 0, 0, 0, 0, 255],    # UV
        ],
        duration=5.0,
    ),
    "warm": Scene(
        name="Warm",
        gradient=[
            [255, 0, 0, 0, 0, 0],    # Red
            [0, 0, 0, 0, 255, 0],    # Amber
            [0, 0, 0, 255, 0, 0],    # White
        ],
        duration=4.0,
    ),
    "cool": Scene(
        name="Cool",
        gradient=[
            [0, 0, 255, 0, 0, 0],    # Blue
            [0, 0, 0, 0, 0, 255],    # UV
            [0, 0, 0, 255, 0, 0],    # White
        ],
        duration=4.0,
    ),
    "rgb": Scene(
        name="RGB",
        gradient=[
            [255, 0, 0, 0, 0, 0],    # Red
            [0, 255, 0, 0, 0, 0],    # Green
            [0, 0, 255, 0, 0, 0],    # Blue
        ],
        duration=3.0,
    ),
    "static_white": Scene(
        name="Static White",
        gradient=[
            [0, 0, 0, 255, 0, 0],    # White
        ],
        duration=1.0,
        loop=False,
    ),
}

# --- MAIN LOOP ---
try:
    start_time = time.time()
    leds_per_universe = LED_COUNT_PER_STRIP * LED_STRIPS_PER_UNIVERSE
    total_leds = leds_per_universe * UNIVERSE_COUNT
    cycle_duration = EFFECT_DURATION + CROSSFADE_DURATION

    print(f"Running {len(EFFECTS)} effects with {CROSSFADE_DURATION}s crossfade...")
    for name, _ in EFFECTS:
        print(f"  - {name}")

    while True:
        t = time.time() - start_time

        # Determine current and next effect
        cycle_position = t % (len(EFFECTS) * cycle_duration)
        effect_index = int(cycle_position // cycle_duration)
        time_in_cycle = cycle_position % cycle_duration

        current_effect_name, current_effect_fn = EFFECTS[effect_index]
        next_effect_name, next_effect_fn = EFFECTS[(effect_index + 1) % len(EFFECTS)]

        # Generate current effect frame
        frame = current_effect_fn(total_leds, t)

        # Check if we're in crossfade period
        if time_in_cycle > EFFECT_DURATION:
            # We're crossfading to next effect
            fade_progress = (time_in_cycle - EFFECT_DURATION) / CROSSFADE_DURATION
            fade_progress = smoothstep(fade_progress)  # Smooth the transition
            next_frame = next_effect_fn(total_leds, t)
            frame = blend_frames(frame, next_frame, fade_progress)

        # Split frame into per-universe chunks and send
        for u, artnet in enumerate(universes):
            start_idx = u * leds_per_universe * COMPONENTS_PER_LED
            end_idx = start_idx + leds_per_universe * COMPONENTS_PER_LED
            artnet.set(frame[start_idx:end_idx])

        time.sleep(0.016)  # ~60Hz update rate

except KeyboardInterrupt:
    # Handle user interruption (Ctrl+C) gracefully
    print("Stopping Art-Net sender.")

finally:
    # It is crucial to clean up and stop the threads when done
    print("Blackout and stop.")
    for artnet in universes:
        artnet.blackout()
        artnet.stop()
    universes.clear()
