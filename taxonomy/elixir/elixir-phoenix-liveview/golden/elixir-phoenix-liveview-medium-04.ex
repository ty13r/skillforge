# golden: tenant-scoped PubSub subscribe+broadcast with connected? and stream
defmodule MyAppWeb.TenantChatLive do
  use MyAppWeb, :live_view

  def mount(%{"org_id" => org_id, "room_id" => room_id}, _session, socket) do
    topic = "chat:org:#{org_id}:room:#{room_id}"

    if connected?(socket) do
      Phoenix.PubSub.subscribe(MyApp.PubSub, topic)
    end

    socket =
      socket
      |> assign(:topic, topic)
      |> assign(:org_id, org_id)
      |> assign(:room_id, room_id)
      |> stream(:messages, [])

    {:ok, socket}
  end

  def handle_event("send", %{"body" => body}, socket) do
    message = %{id: System.unique_integer([:positive]), body: body}
    Phoenix.PubSub.broadcast(MyApp.PubSub, socket.assigns.topic, {:new_message, message})
    {:noreply, socket}
  end

  def handle_info({:new_message, message}, socket) do
    {:noreply, stream_insert(socket, :messages, message)}
  end

  def render(assigns) do
    ~H"""
    <div id="messages" phx-update="stream">
      <div :for={{dom_id, msg} <- @streams.messages} id={dom_id}>
        {msg.body}
      </div>
    </div>
    <form phx-submit="send">
      <input name="body" />
      <button type="submit">Send</button>
    </form>
    """
  end
end
