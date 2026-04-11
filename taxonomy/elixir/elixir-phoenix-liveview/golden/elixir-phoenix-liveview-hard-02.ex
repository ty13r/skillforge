# golden: scoped PubSub chat with connected?/1 guard and per-room topic
defmodule MyAppWeb.ChatLive do
  use MyAppWeb, :live_view

  alias MyApp.Chat

  def mount(%{"room_id" => room_id}, _session, socket) do
    topic = "chat:room:#{room_id}"

    if connected?(socket) do
      Phoenix.PubSub.subscribe(MyApp.PubSub, topic)
    end

    socket =
      socket
      |> assign(:room_id, room_id)
      |> assign(:topic, topic)
      |> stream(:messages, [])

    {:ok, socket}
  end

  def handle_params(_params, _url, socket) do
    messages = Chat.list_messages(socket.assigns.room_id)
    {:noreply, stream(socket, :messages, messages, reset: true)}
  end

  def handle_info({:new_message, message}, socket) do
    {:noreply, stream_insert(socket, :messages, message, at: 0)}
  end

  def handle_event("send", %{"body" => body}, socket) do
    {:ok, message} = Chat.create_message(socket.assigns.room_id, body)
    Phoenix.PubSub.broadcast(MyApp.PubSub, socket.assigns.topic, {:new_message, message})
    {:noreply, socket}
  end

  def render(assigns) do
    ~H"""
    <div id="chat" phx-update="stream">
      <div :for={{id, m} <- @streams.messages} id={id} class="message">
        <strong>{m.author}:</strong> {m.body}
      </div>
    </div>
    <form phx-submit="send">
      <input name="body" type="text" />
      <button type="submit">Send</button>
    </form>
    """
  end
end
