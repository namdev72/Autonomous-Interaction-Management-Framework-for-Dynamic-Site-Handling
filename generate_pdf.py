import markdown
import asyncio
from playwright.async_api import async_playwright
import os

md_path = r"C:\Users\AsusVivoBook\.gemini\antigravity-ide\brain\87896500-7113-43c9-903f-1b402d12f4d1\technical_documentation.md"

def convert():
    with open(md_path, "r", encoding="utf-8") as f:
        md_text = f.read()

    html_content = markdown.markdown(md_text, extensions=['extra'])
    
    # Wrap in basic HTML for professional styling
    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Segoe UI', Arial, sans-serif;
                line-height: 1.6;
                color: #222;
                margin: 40px;
                max-width: 900px;
            }}
            h1 {{ color: #1a365d; border-bottom: 2px solid #2b6cb0; padding-bottom: 10px; margin-bottom: 20px; }}
            h2 {{ color: #2a4365; border-bottom: 1px solid #e2e8f0; padding-bottom: 5px; margin-top: 40px; }}
            h3 {{ color: #2d3748; margin-top: 25px; }}
            code {{ background-color: #edf2f7; padding: 2px 6px; border-radius: 4px; font-family: Consolas, monospace; font-size: 0.9em; }}
            pre {{ background-color: #f7fafc; padding: 15px; border-radius: 6px; border: 1px solid #e2e8f0; overflow-x: auto; }}
            ul {{ padding-left: 25px; }}
            li {{ margin-bottom: 8px; }}
            hr {{ border: 0; height: 1px; background: #e2e8f0; margin: 30px 0; }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """

    with open("temp.html", "w", encoding="utf-8") as f:
        f.write(full_html)

async def generate_pdf():
    print("Launching Chromium to generate PDF...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        url = "file:///" + os.path.abspath("temp.html").replace("\\", "/")
        await page.goto(url)
        
        await page.pdf(
            path="Technical_Documentation.pdf", 
            format="A4", 
            print_background=True, 
            margin={"top": "1in", "bottom": "1in", "left": "1in", "right": "1in"}
        )
        await browser.close()
        
        # Cleanup temp file
        if os.path.exists("temp.html"):
            os.remove("temp.html")

if __name__ == "__main__":
    convert()
    asyncio.run(generate_pdf())
    print("Successfully created Technical_Documentation.pdf!")
