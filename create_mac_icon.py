import os
import sys
from PIL import Image, ImageDraw, ImageFilter

src_path = "/Users/wreckerknight/.gemini/antigravity/brain/b23816e9-53be-4056-a7d1-8e315f187955/media__1784392942806.png"

if not os.path.exists(src_path):
    print("Source image not found!")
    sys.exit(1)

img = Image.open(src_path).convert("RGBA")
w, h = img.size

# Square crop around center
min_dim = min(w, h)
left = (w - min_dim) // 2
top = (h - min_dim) // 2
right = left + min_dim
bottom = top + min_dim

crop_img = img.crop((left, top, right, bottom))
res_img = crop_img.resize((1024, 1024), Image.Resampling.LANCZOS)

# Create 1024x1024 macOS squircle canvas (824x824 icon inside 1024x1024 with margin & rounded corners)
final_canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))

icon_size = 860
inset = (1024 - icon_size) // 2 # 82px margin

resized_inner = res_img.resize((icon_size, icon_size), Image.Resampling.LANCZOS)

# Create rounded rectangle mask for macOS style squircle
mask = Image.new("L", (icon_size, icon_size), 0)
draw = ImageDraw.Draw(mask)
corner_radius = 190
draw.rounded_rectangle((0, 0, icon_size, icon_size), corner_radius, fill=255)

# Apply mask
rounded_inner = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
rounded_inner.paste(resized_inner, (0, 0), mask=mask)

# Add subtle drop shadow
shadow = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
shadow_draw = ImageDraw.Draw(shadow)
shadow_draw.rounded_rectangle((inset, inset + 12, inset + icon_size, inset + icon_size + 12), corner_radius, fill=(0, 0, 0, 160))
shadow = shadow.filter(ImageFilter.GaussianBlur(16))

# Composite shadow + rounded icon
final_canvas.paste(shadow, (0, 0), shadow)
final_canvas.paste(rounded_inner, (inset, inset), mask=rounded_inner)

# Save main 1024x1024 PNG
output_png = "AppIcon.png"
final_canvas.save(output_png, "PNG")
final_canvas.save("public/logo.png", "PNG")
print("Saved AppIcon.png and public/logo.png")

# Create .iconset directory for iconutil
iconset_dir = "AppIcon.iconset"
os.makedirs(iconset_dir, exist_ok=True)

sizes = [
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png")
]

for sz, fname in sizes:
    resized = final_canvas.resize((sz, sz), Image.Resampling.LANCZOS)
    resized.save(os.path.join(iconset_dir, fname))

print("Created AppIcon.iconset directory with all resolutions.")
