# golden: DB-in-mount + unguarded subscribe fix, moved to handle_params + connected?/1 gate
defmodule MyAppWeb.DashboardLive do
  use MyAppWeb, :live_view

  alias MyApp.Accounts
  alias MyApp.Billing
  alias MyApp.Reports

  def mount(_params, _session, socket) do
    current_user = Accounts.get_current_user()

    if connected?(socket) do
      Phoenix.PubSub.subscribe(MyApp.PubSub, "dashboard:user:#{current_user.id}")
    end

    socket =
      socket
      |> assign(:current_user, current_user)
      |> assign(:invoices, [])
      |> assign(:metrics, nil)
      |> assign(:unread_count, 0)

    {:ok, socket}
  end

  def handle_params(_params, _url, socket) do
    current_user = socket.assigns.current_user
    invoices = Billing.list_recent_invoices(current_user.id)
    metrics = Reports.compute_dashboard_metrics(current_user.id)
    unread_count = Accounts.count_unread_notifications(current_user.id)

    socket =
      socket
      |> assign(:invoices, invoices)
      |> assign(:metrics, metrics)
      |> assign(:unread_count, unread_count)

    {:noreply, socket}
  end

  def handle_info({:new_notification, _payload}, socket) do
    {:noreply, update(socket, :unread_count, &(&1 + 1))}
  end
end
