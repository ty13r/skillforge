# fixture: Endpoint module with Phoenix.Ecto.SQL.Sandbox plug in wrong position
defmodule MyAppWeb.Endpoint do
  use Phoenix.Endpoint, otp_app: :my_app

  @session_options [
    store: :cookie,
    key: "_my_app_key",
    signing_salt: "abcdefgh",
    same_site: "Lax"
  ]

  socket "/live", Phoenix.LiveView.Socket,
    websocket: [connect_info: [session: @session_options]]

  plug Plug.Static,
    at: "/",
    from: :my_app,
    gzip: false,
    only: MyAppWeb.static_paths()

  plug Plug.RequestId
  plug Plug.Telemetry, event_prefix: [:phoenix, :endpoint]

  plug Plug.Parsers,
    parsers: [:urlencoded, :multipart, :json],
    pass: ["*/*"],
    json_decoder: Phoenix.json_library()

  plug Plug.MethodOverride
  plug Plug.Head
  plug Plug.Session, @session_options

  # BUG: sandbox plug placed here is too late — must be at the top of endpoint.ex
  # before other plugs so metadata propagates to every request and LV socket.
  if Application.compile_env(:my_app, :sql_sandbox, false) do
    plug Phoenix.Ecto.SQL.Sandbox
  end

  plug MyAppWeb.Router
end
