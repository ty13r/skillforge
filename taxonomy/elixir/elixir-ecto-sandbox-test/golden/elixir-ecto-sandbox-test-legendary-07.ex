# Golden: endpoint.ex with Phoenix.Ecto.SQL.Sandbox plug at the TOP, before any other plugs
defmodule MyAppWeb.Endpoint do
  use Phoenix.Endpoint, otp_app: :my_app

  @session_options [
    store: :cookie,
    key: "_my_app_key",
    signing_salt: "abcdefgh",
    same_site: "Lax"
  ]

  # IMPORTANT: sandbox plug must be at the TOP of endpoint.ex before ANY
  # other plugs, so the sandbox metadata is extracted from request headers
  # and propagated to every downstream plug and the LiveView socket.
  if Application.compile_env(:my_app, :sql_sandbox, false) do
    plug Phoenix.Ecto.SQL.Sandbox
  end

  socket "/live", Phoenix.LiveView.Socket,
    websocket: [connect_info: [:user_agent, session: @session_options]]

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
  plug MyAppWeb.Router
end
