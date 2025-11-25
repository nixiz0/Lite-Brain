from fastapi.templating import Jinja2Templates
from i18n import t, get_js_catalog
from CONFIG import LANGUAGE

templates = Jinja2Templates(directory="templates")
templates.env.globals["t"] = t
templates.env.globals["LANGUAGE"] = LANGUAGE

def render_base(request, template_name: str, context: dict | None = None, **kwargs):
  """
    Helper for rendering a template that extends base.html.
    Always injects request + i18n_js.
  """
  ctx = {"request": request, "i18n_js": get_js_catalog()}
  if context:
      ctx.update(context)
  return templates.TemplateResponse(template_name, ctx, **kwargs)
