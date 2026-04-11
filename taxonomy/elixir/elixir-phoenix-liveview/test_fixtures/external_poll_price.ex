# fixture: LiveView polls an external API per user — should be a single GenServer + broadcast
defmodule MyAppWeb.PriceTickerLive do
  use MyAppWeb, :live_view

  alias MyApp.HTTPClient

  def mount(_params, _session, socket) do
    # ANTI-PATTERN: every connected user polls the upstream API every second,
    # multiplying the request count by the connected user count.
    if connected?(socket), do: :timer.send_interval(1000, self(), :tick)
    {:ok, assign(socket, :price, nil)}
  end

  def handle_info(:tick, socket) do
    case HTTPClient.fetch_price("BTC") do
      {:ok, price} -> {:noreply, assign(socket, :price, price)}
      {:error, _} -> {:noreply, socket}
    end
  end

  def render(assigns) do
    ~H"""
    <div>
      <h1>BTC price</h1>
      <%= if @price do %>
        <p class="price">${@price}</p>
      <% else %>
        <p>Loading…</p>
      <% end %>
    </div>
    """
  end
end
