import time
import random
from stupidArtnet.StupidArtnet import StupidArtnet

# --- USER CONFIG ---
# IP address of the DMX receiver (e.g., an Art-Net node or lighting console)
TARGET_IP = '10.0.1.95' 

# The universe number to send data to (0-indexed)
UNIVERSE = 0
# RGBWAUV
COMPONENTS_PER_LED = 6
# 18 Leds per light strip
LED_COUNT_PER_STRIP = 18
# 3 strips per universe
LED_STRIPS_PER_UNIVERSE = 3
# The size of the DMX packet (usually 512 channels)
PACKET_SIZE = COMPONENTS_PER_LED * LED_COUNT_PER_STRIP * LED_STRIPS_PER_UNIVERSE
# --- END USER CONFIG ---

# Create a StupidArtnet instance
a = StupidArtnet(TARGET_IP, UNIVERSE, PACKET_SIZE)

# Start the persistent sending thread
# This sends the current buffer repeatedly at a high frequency (around 30Hz)
a.start() 
print(f"Sending Art-Net to {TARGET_IP} Universe {UNIVERSE}...")

def make_amber(fader=None):
    # RGBWAUV format: R=0, G=1, B=2, W=3, A=4, UV=5
    b = bytearray(6)
    if fader:
        b[4] = random.randint(160, 255)
    else:
        b[4] = 255     # amber
    return b
 

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
    # Example loop to continuously modify and send data
    for x in range(100):
        # Create a new DMX packet buffer
        packet = bytearray(PACKET_SIZE)
        
        # # Fill the buffer with random data for demonstration
        # for i in range(PACKET_SIZE):
        #     packet[i] = random.randint(0, 255)
        # a.set(packet)

        result = bytearray()
        for i in range(LED_COUNT_PER_STRIP * LED_STRIPS_PER_UNIVERSE):
            result = result + make_amber(fader=True)

        # Update the internal buffer (the thread will send this new data)
        print(f"len={len(result)}, first 12 bytes: {list(result[:12])}")
        # Expected RGBWAUV: [0,1,2,3,4,5] = [R,G,B,W,A,UV]
        # With 4-byte prefix, first fixture starts at index 4
        # So amber (index 4 in fixture) should be at raw index 8
        a.set(result)
        
        # Wait for a short duration before sending the next random values
        time.sleep(0.25)

except KeyboardInterrupt:
    # Handle user interruption (Ctrl+C) gracefully
    print("Stopping Art-Net sender.")

finally:
    # It is crucial to clean up and stop the thread when done
    print("Blackout and stop.")
    a.blackout() # Optional: sends a packet with all zeros
    a.stop()
    del a
