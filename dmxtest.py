import time
import random
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

def gradient_color(gradient_stops, progress):
    """
    Get interpolated color from gradient stops at given progress (0.0 to 1.0).
    gradient_stops: list of [R, G, B, W, A, UV] colors
    """
    if progress <= 0:
        return gradient_stops[0]
    if progress >= 1:
        return gradient_stops[-1]

    # Find which segment we're in
    num_segments = len(gradient_stops) - 1
    segment_progress = progress * num_segments
    segment_index = int(segment_progress)
    segment_t = segment_progress - segment_index

    # Clamp segment_index to valid range
    if segment_index >= num_segments:
        segment_index = num_segments - 1
        segment_t = 1.0

    return lerp_color(gradient_stops[segment_index], gradient_stops[segment_index + 1], segment_t)

# Define gradient: cycle through all 6 components
GRADIENT = [
    [255, 0, 0, 0, 0, 0],    # Red
    [0, 255, 0, 0, 0, 0],    # Green
    [0, 0, 255, 0, 0, 0],    # Blue
    [0, 0, 0, 255, 0, 0],    # White
    [0, 0, 0, 0, 255, 0],    # Amber
    [0, 0, 0, 0, 0, 255],    # UV
]

# Duration of one full gradient cycle in seconds
CYCLE_DURATION = 5.0
 

# packet = bytearray(PACKET_SIZE)

# packet[0] = 255
# packet[1] = 255
# packet[2] = 255
# packet[3] = 1

# packet[4] = 0      #red
# packet[5] = 0     # green
# packet[6] = 0       # blue
# packet[7] = 0       #white
# packet[8] = 255     # amber
# packet[9] = 0       # violet

# packet[106] = 0      #red
# packet[107] = 0     # green
# packet[108] = 0       # blue
# packet[109] = 0       #white
# packet[110] = 255     # amber
# packet[111] = 0       # violet

try:
    start_time = time.time()
    leds_per_universe = LED_COUNT_PER_STRIP * LED_STRIPS_PER_UNIVERSE

    while True:
        # Calculate progress through the gradient cycle (0.0 to 1.0)
        elapsed = time.time() - start_time
        progress = (elapsed % CYCLE_DURATION) / CYCLE_DURATION

        # Get the current color from the gradient
        current_color = gradient_color(GRADIENT, progress)
        led_bytes = make_color(current_color)

        # Send the same color to all LEDs in all universes
        for artnet in universes:
            result = bytearray()
            for i in range(leds_per_universe):
                result = result + led_bytes
            artnet.set(result)

        print(f"progress={progress:.2f}, color={[int(c) for c in current_color]}")

        time.sleep(0.03)  # ~30Hz update rate

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
