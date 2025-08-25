Browser Use 0.6.1 — Dev Notes (for coding agents)

Version + install

Latest release: 0.6.1 (“Bugfixes and performance boost”). Prior release 0.6.0 = major engine change. 
GitHub

Python 3.11+. Install with pip install browser-use. If you need a Chromium binary locally, the README shows a quick uvx playwright install chromium step (this only fetches Chromium; runtime is not Playwright). 
GitHub

Big breaking change

Playwright is no longer the driver. From 0.6.0 onward, Browser Use talks directly to Chrome via CDP using the new cdp-use + bubus libs. Don’t write code against Playwright Page/Context—use the Browser Use APIs. 
GitHub

The team’s post “Closer to the Metal: Leaving Playwright for CDP” explains the switch + perf/robustness gains. 
browser-use.com

Docs are in the middle of being cleaned up, so you’ll still see some Playwright phrasing/examples; issue #2749 tracks this. Treat any Page references as outdated. 
GitHub

Core objects you’ll use

Agent — orchestrates the task:
Agent(task=..., llm=..., controller=optional, use_vision=True, save_conversation_path=..., initial_actions=[...])
Vision is on by default; you can disable and/or tune vision_detail_level. 
docs.browser-use.com

BrowserSession / BrowserProfile — configure/launch or connect over CDP:
BrowserSession(cdp_url=..., browser_pid=..., executable_path=..., allowed_domains=[...], keep_alive=True, stealth=True, ...)
You can launch a local Chrome/Chromium, attach to an existing pid, or connect to a remote CDP URL. 
docs.browser-use.com
+2
docs.browser-use.com
+2

Models — wrappers provided: ChatOpenAI, ChatAnthropic, ChatGoogle, ChatGroq, ChatOllama, etc. Note for Gemini: use GOOGLE_API_KEY (renamed from GEMINI_API_KEY). 
docs.browser-use.com

Custom actions (tools)

Register with a Controller:

controller = Controller()

@controller.action("Click element")
async def click_element(css_selector: str, browser_session: BrowserSession) -> ActionResult:
    cdp = await browser_session.get_or_create_cdp_session()
    await cdp.cdp_client.send.Runtime.evaluate(
        params={'expression': f'document.querySelector("{css_selector}").click()'},
        session_id=cdp.session_id,
    )
    return ActionResult(extracted_content=f"Clicked {css_selector}")


Pass controller=controller into Agent(...). Always return ActionResult | str | None; type hints are required. 
docs.browser-use.com

Interacting with the browser (CDP & events)

Direct CDP: cdp = await browser_session.get_or_create_cdp_session(); await cdp.cdp_client.send.Page.navigate(...). 
docs.browser-use.com

Event bus (higher-level): dispatch NavigateToUrlEvent, ClickElementEvent, TypeTextEvent, etc., and await them. 
docs.browser-use.com

Handy session helpers: take_screenshot(), get_page_html(), get_tabs(), get_browser_state_summary(). 
docs.browser-use.com

Running + debugging

history = await agent.run() → inspect history.urls(), history.screenshot_paths(), history.action_names(), history.final_result() and more for analysis/debug. 
docs.browser-use.com

Minimal example (0.6.1-style)

import asyncio
from browser_use import Agent, BrowserSession, ChatOpenAI

async def main():
    llm = ChatOpenAI(model="gpt-4.1-mini")
    session = BrowserSession(  # launch or connect; CDP under the hood
        allowed_domains=['https://www.google.com', 'https://*.wikipedia.org'],
        keep_alive=True,
        headless=True,
    )
    agent = Agent(
        task="Find the number of stars of the browser-use repo",
        llm=llm,
        browser_session=session,
        use_vision=True,
        save_conversation_path="./logs/convo",
    )
    history = await agent.run()
    print(history.final_result())

asyncio.run(main())


Gotchas to avoid

❌ Don’t import or pass Playwright Page/Context to functions (no longer supported). Use BrowserSession + CDP/event APIs instead. 
docs.browser-use.com

❌ Don’t assume docs mentioning Playwright imply runtime dependency—it’s mostly config semantics carried forward; the driver is CDP now. 