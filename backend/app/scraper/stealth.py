from playwright.async_api import Page
from playwright_stealth import Stealth

WEBDRIVER_PATCH = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
"""

PLUGINS_PATCH = """
Object.defineProperty(navigator, 'plugins', {
    get: () => [1, 2, 3, 4, 5].map(() => ({
        name: 'Chrome PDF Plugin',
        description: 'Portable Document Format',
        filename: 'internal-pdf-viewer',
        length: 1,
    })),
});
"""

WEBGL_PATCH = """
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function(parameter) {
    if (parameter === 37445) return 'Intel Inc.';
    if (parameter === 37446) return 'Intel Iris OpenGL Engine';
    return getParameter.call(this, parameter);
};
"""

CHROME_RUNTIME_PATCH = """
window.chrome = { runtime: {}, loadTimes: function(){}, csi: function(){} };
"""

PERMISSIONS_PATCH = """
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) =>
    parameters.name === 'notifications'
        ? Promise.resolve({ state: Notification.permission })
        : originalQuery(parameters);
"""

STEALTH_SCRIPTS = {
    "minimal": [WEBDRIVER_PATCH],
    "standard": [WEBDRIVER_PATCH, PLUGINS_PATCH, CHROME_RUNTIME_PATCH],
    "full": [WEBDRIVER_PATCH, PLUGINS_PATCH, WEBGL_PATCH, CHROME_RUNTIME_PATCH, PERMISSIONS_PATCH],
}


_stealth = Stealth()


async def apply_stealth(page: Page, level: str = "full") -> None:
    await _stealth.apply_stealth_async(page)
    scripts = STEALTH_SCRIPTS.get(level, STEALTH_SCRIPTS["full"])
    for script in scripts:
        await page.add_init_script(script)
