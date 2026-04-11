# fixture: LiveView-era CSP policy weakened to 'unsafe-inline' to "fix" breakage
# Vulnerability: removing 'self' in favor of 'unsafe-inline' because the
# developer didn't know about CSP nonces. Fix uses a nonce plug + {@csp_nonce}.
defmodule MyAppWeb.Router do
  use MyAppWeb, :router

  pipeline :browser do
    plug :accepts, ["html"]
    plug :fetch_session
    plug :fetch_live_flash
    plug :put_root_layout, html: {MyAppWeb.Layouts, :root}
    plug :put_secure_browser_headers, %{
      "content-security-policy" =>
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    }
  end

  scope "/", MyAppWeb do
    pipe_through :browser
    live "/posts", PostLive.Index, :index
  end
end
