# fixture: Controller with three distinct vulnerabilities of different severity
# Vulnerabilities:
#  1. Atom exhaustion (HIGH): String.to_atom(params["scope"])
#  2. Open redirect (HIGH): redirect(external: params["next"])
#  3. Timing attack (MED): if conn.assigns.csrf == received
# Tests the foundation capability — prioritized multi-fix response.
defmodule MyAppWeb.AdminController do
  use MyAppWeb, :controller

  def dashboard(conn, params) do
    scope = String.to_atom(params["scope"] || "all")
    metrics = MyApp.Analytics.fetch(scope)
    render(conn, :dashboard, metrics: metrics)
  end

  def update_settings(conn, %{"csrf_token" => received} = params) do
    if conn.assigns.csrf == received do
      MyApp.Settings.update(params)
      redirect(conn, external: params["next"])
    else
      send_resp(conn, 403, "Invalid token")
    end
  end
end
