import os
from PIL import Image, ImageDraw, ImageFont

class SlideGenerator:
    def __init__(self, width=1920, height=1080):
        self.width = width
        self.height = height
        self.bg_color = (18, 18, 18)  # Premium Dark (#121212)
        self.text_color = (255, 255, 255)
        self.accent_color = (187, 134, 252)  # #BB86FC
        
        # Try to find a system font
        self.font_path = self._find_font()

    def _find_font(self):
        # Common paths for Linux (Docker)
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
            "C:\\Windows\\Fonts\\arialbd.ttf"  # Local Windows
        ]
        for p in paths:
            if os.path.exists(p):
                return p
        return None  # Fallback to default PIL font if none found

    def generate_slide(self, title, content, output_path):
        # Create a new image
        img = Image.new("RGB", (self.width, self.height), color=self.bg_color)
        draw = ImageDraw.Draw(img)
        
        # Load fonts
        try:
            if self.font_path:
                title_font = ImageFont.truetype(self.font_path, 80)
                content_font = ImageFont.truetype(self.font_path, 50)
            else:
                title_font = ImageFont.load_default()
                content_font = ImageFont.load_default()
        except:
            title_font = ImageFont.load_default()
            content_font = ImageFont.load_default()

        # Draw accent bar
        draw.rectangle([50, 50, 100, self.height - 50], fill=self.accent_color)

        # Draw title
        draw.text((150, 100), title, font=title_font, fill=self.accent_color)
        
        # Draw content (simple line-by-line wrapping for now)
        draw.text((150, 250), content, font=content_font, fill=self.text_color)
        
        # Save the image
        img.save(output_path)
        return output_path
