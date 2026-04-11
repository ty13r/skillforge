# golden: convert a large-list assign to stream/3 with proper container + dom ids
defmodule MyAppWeb.InboxLive do
  use MyAppWeb, :live_view

  alias MyApp.Messaging

  def mount(_params, %{"user_id" => user_id}, socket) do
    socket =
      socket
      |> assign(:user_id, user_id)
      |> assign(:filter, :all)
      |> assign(:message_count, 0)

    {:ok, socket}
  end

  def handle_params(_params, _url, socket) do
    messages = Messaging.list_messages_for_user(socket.assigns.user_id)

    socket =
      socket
      |> stream(:messages, messages, reset: true)
      |> assign(:message_count, length(messages))

    {:noreply, socket}
  end

  def render(assigns) do
    ~H"""
    <div class="inbox">
      <h1>Inbox ({@message_count})</h1>
      <div id="messages" phx-update="stream" class="messages">
        <div :for={{dom_id, msg} <- @streams.messages} id={dom_id} class="message">
          <div class="from">{msg.from}</div>
          <div class="subject">{msg.subject}</div>
        </div>
      </div>
    </div>
    """
  end

  def handle_event("delete", %{"id" => id}, socket) do
    msg = Messaging.get_message!(id)
    {:ok, _} = Messaging.delete_message(msg)

    socket =
      socket
      |> stream_delete(:messages, msg)
      |> update(:message_count, &(&1 - 1))

    {:noreply, socket}
  end

  def handle_info({:new_message, message}, socket) do
    socket =
      socket
      |> stream_insert(:messages, message, at: 0)
      |> update(:message_count, &(&1 + 1))

    {:noreply, socket}
  end
end
