# fixture: Router + LiveView that does not register the sandbox on_mount hook
defmodule MyAppWeb.Router do
  use MyAppWeb, :router

  pipeline :browser do
    plug :accepts, ["html"]
    plug :fetch_session
    plug :fetch_live_flash
    plug :put_root_layout, html: {MyAppWeb.Layouts, :root}
    plug :protect_from_forgery
    plug :put_secure_browser_headers
  end

  pipeline :require_authenticated_user do
    plug :fetch_current_user
    plug :ensure_authenticated
  end

  scope "/", MyAppWeb do
    pipe_through [:browser, :require_authenticated_user]

    # BUG: this live_session needs {MyAppWeb.UserAuth, :mount_current_user} for auth
    # AND a sandbox on_mount hook — otherwise the LV process has no DB connection
    # in tests that use Phoenix.Ecto.SQL.Sandbox.
    live_session :authenticated,
      on_mount: [{MyAppWeb.UserAuth, :mount_current_user}] do
      live "/dashboard", DashboardLive
    end
  end
end
