import asyncio, os, sys
import pyotp
from playwright.async_api import async_playwright

BASE = os.environ["BASE_URL"]
OUT = "/app/frontend/public/formazione"
PAGES = [
    ("dashboard", "/"), ("clienti", "/clienti"), ("riparazioni", "/riparazioni"), ("telefonia", "/telefonia"),
    ("magazzino", "/magazzino"), ("ritiri", "/ritiri"), ("negozi", "/negozi"), ("whatsapp", "/whatsapp"),
    ("portali", "/portali"), ("password", "/password"), ("sicurezza", "/sicurezza"), ("registro-accessi", "/registro-accessi"),
    ("formazione", "/formazione"), ("utenti", "/utenti"),
]

async def main():
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        page = await b.new_page(viewport={"width": 1440, "height": 860}, device_scale_factor=1)
        await page.goto(f"{BASE}/login")
        await page.fill('input[type="email"]', "rsriparazioni@gmail.com")
        await page.fill('input[type="password"]', "Devis2026!")
        await page.click('button[type="submit"]')
        await page.wait_for_timeout(1500)
        await page.locator("input").first.fill(pyotp.TOTP(os.environ["TEST_ADMIN_TOTP_SECRET"]).now())
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(3000)
        await page.screenshot(path=f"{OUT}/login.png", type="jpeg", quality=70) if False else None
        for name, path in PAGES:
            try:
                link = page.locator(f'a[href="{path}"]').first
                if await link.count():
                    await link.click(force=True)
                else:
                    await page.goto(f"{BASE}{path}", wait_until="commit", timeout=60000)
            except Exception as e:
                print("skip", name, str(e)[:80]); continue
            await page.wait_for_timeout(3500)
            await page.add_style_tag(content="table tbody td, [data-testid^='rip-card'], [data-testid^='password-card'] pre, [data-testid^='password-card'] span.font-mono { filter: blur(5px) !important; }")
            await page.wait_for_timeout(300)
            await page.screenshot(path=f"{OUT}/{name}.jpg", type="jpeg", quality=72)
            print("ok", name)
        # login page (fresh context)
        ctx = await b.new_context(viewport={"width": 1440, "height": 860})
        pg = await ctx.new_page()
        await pg.goto(f"{BASE}/login"); await pg.wait_for_timeout(2000)
        await pg.screenshot(path=f"{OUT}/login.jpg", type="jpeg", quality=72); print("ok login")
        await b.close()

asyncio.run(main())
