# golden: multi-vuln controller fix — all three issues addressed
defmodule MyAppWeb.AdminController do
  use MyAppWeb, :controller

  @scopes %{"all" => :all, "active" => :active, "archived" => :archived}

  def dashboard(conn, params) do
    scope = Map.get(@scopes, params["scope"], :all)
    metrics = MyApp.Analytics.fetch(scope)
    render(conn, :dashboard, metrics: metrics)
  end

  def update_settings(conn, %{"csrf_token" => received} = params) do
    if Plug.Crypto.secure_compare(conn.assigns.csrf, received) do
      MyApp.Settings.update(params)
      redirect(conn, to: "/admin/dashboard")
    else
      send_resp(conn, 403, "Invalid token")
    end
  end
end
