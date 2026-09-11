import os
from PIL import Image, ImageDraw

def mask_logo(input_path, output_path):
    print(f"Masking {input_path} to macOS squircle design...")
    # Open original image and convert to RGBA
    img = Image.open(input_path).convert("RGBA")
    
    # Resize to standard high-res macOS app icon size: 1024x1024
    img = img.resize((1024, 1024), Image.Resampling.LANCZOS)
    
    # Create transparent mask
    mask = Image.new("L", (1024, 1024), 0)
    draw = ImageDraw.Draw(mask)
    
    # Modern macOS squircle bounding box inside 1024x1024 image.
    # The generated squircle starts around 145px from edges.
    left, top = 145, 145
    right, bottom = 879, 879
    radius = 162
    
    # Draw rounded rect mask
    draw.rounded_rectangle(
        [left, top, right, bottom],
        radius=radius,
        fill=255
    )
    
    # Apply mask to image
    output = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    output.paste(img, (0, 0), mask=mask)
    
    # Save as PNG
    output.save(output_path, "PNG")
    print("Successfully masked and saved logo with transparent corners.")

if __name__ == "__main__":
    mask_logo("logo.png", "logo.png")
