# fixture: LiveView that passes %Socket{} into helper functions — the socket-leak anti-pattern
defmodule MyAppWeb.ReportLive do
  use MyAppWeb, :live_view

  alias MyApp.Reports

  def mount(_params, _session, socket) do
    socket =
      socket
      |> assign(:current_user, %{id: 1, org_id: 7, name: "Ada"})
      |> assign(:report_date, Date.utc_today())
      |> assign(:raw_data, [])

    {:ok, socket}
  end

  def handle_params(_params, _url, socket) do
    socket = fetch_report(socket)
    {:noreply, socket}
  end

  # ANTI-PATTERN: the entire socket is passed into a helper that only needs 2 assigns
  defp fetch_report(socket) do
    data = Reports.load(socket.assigns.current_user.org_id, socket.assigns.report_date)
    assign(socket, :raw_data, data)
  end

  # ANTI-PATTERN: helper takes socket to read a single field for formatting
  defp format_header(socket) do
    "Report for #{socket.assigns.current_user.name} on #{socket.assigns.report_date}"
  end

  # ANTI-PATTERN: helper takes socket to compute a derived value
  defp chart_data(socket) do
    Enum.map(socket.assigns.raw_data, fn row ->
      %{x: row.label, y: row.amount}
    end)
  end

  def render(assigns) do
    ~H"""
    <div>
      <h1>{format_header(@socket)}</h1>
      <MyAppWeb.Charts.bars data={chart_data(@socket)} />
    </div>
    """
  end
end
