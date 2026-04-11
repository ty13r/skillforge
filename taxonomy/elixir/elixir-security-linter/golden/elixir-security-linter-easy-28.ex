# golden: session/cookie security fix — http_only, secure, proper salt
defmodule MyAppWeb.Endpoint do
  use Phoenix.Endpoint, otp_app: :my_app

  @session_options [
    store: :cookie,
    key: "_my_app_key",
    signing_salt: {MyAppWeb.SessionSalt, :get, []},
    same_site: "Lax",
    http_only: true,
    secure: true,
    max_age: 60 * 60 * 24 * 7
  ]

  plug Plug.Session, @session_options

  plug Plug.Static,
    at: "/",
    from: :my_app,
    gzip: false,
    only: ~w(assets fonts images favicon.ico robots.txt)

  plug MyAppWeb.Router
end
