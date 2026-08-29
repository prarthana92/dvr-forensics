"""
Creates a small synthetic file with the Hikvision signature planted
at the correct offset, purely to test that detector.py reads the
right byte position. This is NOT real Hikvision data -- it only
proves our code looks in the right place.
"""

def make_fake_hikvision_image(path):
    with open(path, "wb") as f:
        f.write(b"\x00" * 0x200)              # padding up to offset 0x200
        f.write(b"HIKVISION@HANGZHOU")         # the real signature
        f.write(b"\x00" * 1000)                # padding to simulate more disk

if __name__ == "__main__":
    make_fake_hikvision_image("fake_hikvision_test.img")
    print("Created fake_hikvision_test.img")