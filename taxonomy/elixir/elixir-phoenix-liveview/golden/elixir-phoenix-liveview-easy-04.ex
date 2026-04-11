# golden: add connected?/1 guard around PubSub subscribe
defmodule MyAppWeb.FeedLive do
  use MyAppWeb, :live_view

  def mount(_params, _session, socket) do
    if connected?(socket) do
      Phoenix.PubSub.subscribe(MyApp.PubSub, "feed:user:1")
    end

    {:ok, assign(socket, :items, [])}
  end

  def handle_info({:new_item, item}, socket) do
    {:noreply, update(socket, :items, &[item | &1])}
  end

  def render(assigns) do
    ~H"""
    <ul>
      <li :for={i <- @items}>{i.text}</li>
    </ul>
    """
  end
end
