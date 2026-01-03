import time
import random
import math
from stupidArtnet.StupidArtnet import StupidArtnet

# --- USER CONFIG ---
# IP address of the DMX receiver (e.g., an Art-Net node or lighting console)
TARGET_IP = '10.0.1.95' 

# Number of universes (0-indexed, so 4 means universes 0, 1, 2, 3)
UNIVERSE_COUNT = 4
# RGBWAUV
COMPONENTS_PER_LED = 6
# 18 Leds per light strip
LED_COUNT_PER_STRIP = 18
# 3 strips per universe
LED_STRIPS_PER_UNIVERSE = 3
# The size of the DMX packet (usually 512 channels)
PACKET_SIZE = COMPONENTS_PER_LED * LED_COUNT_PER_STRIP * LED_STRIPS_PER_UNIVERSE
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

def make_color(color):
    """Create a 6-byte RGBWAUV color from a list/tuple of 6 values."""
    b = bytearray(6)
    for i, v in enumerate(color):
        b[i] = int(v)
    return b

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

# Flame color palette: dark red -> red -> amber -> yellow-green (flame tip)
FLAME_COLORS = [
    [40, 0, 0, 0, 0, 0],       # Dark red (low flame)
    [255, 0, 0, 0, 80, 0],     # Red + some amber
    [255, 30, 0, 0, 200, 0],   # Red + green hint + amber (mid flame)
    [200, 80, 0, 0, 255, 0],   # More green + full amber (hot)
    [150, 120, 0, 0, 255, 0],  # Green-yellow + amber (flame tip)
]

def get_flame_color(intensity):
    """Map intensity (0.0-1.0) to flame color."""
    return gradient_color(FLAME_COLORS, intensity)

def generate_flame_frame(total_leds, t):
    """Generate a full frame of flame effect for all LEDs."""
    result = bytearray()
    for i in range(total_leds):
        intensity = flame_noise(i, t)
        color = get_flame_color(intensity)
        result += make_color(color)
    return result


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

# --- ACTIVE EFFECT ---
ACTIVE_EFFECT = "flame"  # Options: "flame", "scenes"

# Scene playback settings (for "scenes" effect)
SCENE_DURATION = 5.0  # seconds per scene
scene_list = list(SCENES.values())

try:
    start_time = time.time()
    leds_per_universe = LED_COUNT_PER_STRIP * LED_STRIPS_PER_UNIVERSE
    total_leds = leds_per_universe * UNIVERSE_COUNT

    print(f"Running effect: {ACTIVE_EFFECT}")

    while True:
        t = time.time() - start_time

        if ACTIVE_EFFECT == "flame":
            # Generate flame effect for all LEDs across all universes
            frame = generate_flame_frame(total_leds, t)

            # Split frame into per-universe chunks and send
            for u, artnet in enumerate(universes):
                start = u * leds_per_universe * COMPONENTS_PER_LED
                end = start + leds_per_universe * COMPONENTS_PER_LED
                artnet.set(frame[start:end])

        else:  # scenes
            scene_index = int(t // SCENE_DURATION) % len(scene_list)
            current_scene = scene_list[scene_index]
            progress = (t % SCENE_DURATION) / SCENE_DURATION
            current_color = current_scene.get_color(progress)
            led_bytes = make_color(current_color)

            for artnet in universes:
                result = bytearray()
                for i in range(leds_per_universe):
                    result += led_bytes
                artnet.set(result)

        time.sleep(0.016)  # ~60Hz update rate for smoother animation

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
