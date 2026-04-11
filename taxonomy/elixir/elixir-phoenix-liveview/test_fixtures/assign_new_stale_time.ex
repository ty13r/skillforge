# fixture: LiveView using assign_new for a value that must refresh on reconnect
defmodule MyAppWeb.ClockLive do
  use MyAppWeb, :live_view

  def mount(_params, _session, socket) do
    # ANTI-PATTERN: assign_new silently skips on reconnect if the key is already set,
    # so `:now` stays at the originally-rendered HTTP time even after a 10-minute
    # WS disconnect/reconnect.
    socket =
      socket
      |> assign_new(:now, fn -> DateTime.utc_now() end)
      |> assign_new(:render_count, fn -> 0 end)

    if connected?(socket) do
      :timer.send_interval(1000, self(), :tick)
    end

    {:ok, socket}
  end

  def handle_info(:tick, socket) do
    {:noreply, assign(socket, :now, DateTime.utc_now())}
  end

  def render(assigns) do
    ~H"""
    <div>
      <p>Now: {@now}</p>
      <p>Render count: {@render_count}</p>
    </div>
    """
  end
end
