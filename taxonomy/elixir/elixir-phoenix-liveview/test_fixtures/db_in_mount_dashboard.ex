# fixture: LiveView with database queries in mount/3 — the canonical "NO DATABASE QUERIES IN MOUNT" anti-pattern
defmodule MyAppWeb.DashboardLive do
  use MyAppWeb, :live_view

  alias MyApp.Accounts
  alias MyApp.Billing
  alias MyApp.Reports

  # ANTI-PATTERN: every query in here runs twice (once on HTTP, once on WS)
  def mount(_params, _session, socket) do
    current_user = Accounts.get_current_user()
    invoices = Billing.list_recent_invoices(current_user.id)
    metrics = Reports.compute_dashboard_metrics(current_user.id)
    unread_count = Accounts.count_unread_notifications(current_user.id)

    # Another anti-pattern: subscribing without connected?/1 guard
    Phoenix.PubSub.subscribe(MyApp.PubSub, "dashboard:#{current_user.id}")

    socket =
      socket
      |> assign(:current_user, current_user)
      |> assign(:invoices, invoices)
      |> assign(:metrics, metrics)
      |> assign(:unread_count, unread_count)

    {:ok, socket}
  end

  def handle_params(_params, _url, socket) do
    {:noreply, socket}
  end

  def handle_info({:new_notification, _payload}, socket) do
    {:noreply, update(socket, :unread_count, &(&1 + 1))}
  end
end
