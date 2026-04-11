# golden: plug security middleware — add CSP + HSTS + strict headers
defmodule MyAppWeb.Router do
  use MyAppWeb, :router

  pipeline :browser do
    plug :accepts, ["html"]
    plug :fetch_session
    plug :fetch_live_flash
    plug :put_root_layout, html: {MyAppWeb.Layouts, :root}
    plug :put_secure_browser_headers, %{
      "content-security-policy" => "default-src 'self'; object-src 'none'; base-uri 'self'",
      "strict-transport-security" => "max-age=31536000; includeSubDomains",
      "x-frame-options" => "DENY",
      "x-content-type-options" => "nosniff",
      "referrer-policy" => "strict-origin-when-cross-origin"
    }
    plug :protect_from_forgery
  end

  pipeline :api do
    plug :accepts, ["json"]
    plug :protect_from_forgery
  end

  scope "/", MyAppWeb do
    pipe_through :browser
    get "/", PageController, :home
    post "/unsubscribe", NewsletterController, :unsubscribe
  end

  scope "/api", MyAppWeb do
    pipe_through :api
    delete "/posts/:id", PostController, :delete
  end
end
