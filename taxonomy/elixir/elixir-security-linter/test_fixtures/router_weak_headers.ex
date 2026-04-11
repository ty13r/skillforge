# fixture: Router with weak browser headers + API pipeline missing CSRF
# Vulnerability: put_secure_browser_headers without a CSP, unsafe-inline in
# explicit CSP, and an :api pipeline that skips :protect_from_forgery while
# sharing the session cookie with :browser.
defmodule MyAppWeb.Router do
  use MyAppWeb, :router

  pipeline :browser do
    plug :accepts, ["html"]
    plug :fetch_session
    plug :fetch_live_flash
    plug :put_root_layout, html: {MyAppWeb.Layouts, :root}
    plug :put_secure_browser_headers, %{
      "content-security-policy" => "default-src * 'unsafe-inline' 'unsafe-eval'",
      "strict-transport-security" => "max-age=0"
    }
  end

  pipeline :api do
    plug :accepts, ["json"]
    plug :fetch_session
  end

  scope "/", MyAppWeb do
    pipe_through :browser

    get "/", PageController, :home
    get "/unsubscribe", NewsletterController, :unsubscribe
  end

  scope "/api", MyAppWeb do
    pipe_through :api

    post "/posts/:id/delete", PostController, :delete
  end
end
