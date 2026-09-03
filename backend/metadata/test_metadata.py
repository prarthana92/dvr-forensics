from metadata import extract_metadata

video_path = "../device/hikvision_test.mp4"

metadata = extract_metadata(video_path)

print("\nMetadata received by another backend file:")
print(metadata)