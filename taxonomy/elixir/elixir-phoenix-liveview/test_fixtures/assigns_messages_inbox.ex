# fixture: large collection loaded into regular assigns — should be a stream
defmodule MyAppWeb.InboxLive do
  use MyAppWeb, :live_view

  alias MyApp.Messaging

  def mount(_params, %{"user_id" => user_id}, socket) do
    # ~12,000 messages loaded into socket memory
    messages = Messaging.list_messages_for_user(user_id)

    socket =
      socket
      |> assign(:user_id, user_id)
      |> assign(:messages, messages)
      |> assign(:filter, :all)

    {:ok, socket}
  end

  def render(assigns) do
    ~H"""
    <div class="inbox">
      <h1>Inbox ({length(@messages)})</h1>
      <div class="messages">
        <%= for msg <- @messages do %>
          <div class="message" id={"msg-#{msg.id}"}>
            <div class="from">{msg.from}</div>
            <div class="subject">{msg.subject}</div>
          </div>
        <% end %>
      </div>
    </div>
    """
  end

  def handle_event("delete", %{"id" => id}, socket) do
    Messaging.delete_message!(id)
    messages = Enum.reject(socket.assigns.messages, &(&1.id == id))
    {:noreply, assign(socket, :messages, messages)}
  end

  def handle_info({:new_message, message}, socket) do
    {:noreply, update(socket, :messages, &[message | &1])}
  end
end
