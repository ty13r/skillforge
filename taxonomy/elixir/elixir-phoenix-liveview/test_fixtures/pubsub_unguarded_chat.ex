# fixture: chat LiveView missing connected?/1 guard + unscoped PubSub topic
defmodule MyAppWeb.ChatLive do
  use MyAppWeb, :live_view

  alias MyApp.Chat

  def mount(%{"room_id" => room_id}, _session, socket) do
    # ANTI-PATTERN: subscribing without connected?/1 guard
    # ANTI-PATTERN: topic is "messages" — no scoping by room_id, leaks across rooms
    Phoenix.PubSub.subscribe(MyApp.PubSub, "messages")

    messages = Chat.list_messages(room_id)

    socket =
      socket
      |> assign(:room_id, room_id)
      |> assign(:messages, messages)

    {:ok, socket}
  end

  def handle_info({:new_message, message}, socket) do
    {:noreply, update(socket, :messages, &[message | &1])}
  end

  def handle_event("send", %{"body" => body}, socket) do
    {:ok, message} = Chat.create_message(socket.assigns.room_id, body)
    # ANTI-PATTERN: broadcast on unscoped topic
    Phoenix.PubSub.broadcast(MyApp.PubSub, "messages", {:new_message, message})
    {:noreply, socket}
  end
end
