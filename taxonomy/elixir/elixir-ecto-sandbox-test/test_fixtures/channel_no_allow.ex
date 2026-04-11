# fixture: Phoenix Channel missing sandbox allow — channel process has no DB connection
defmodule MyAppWeb.RoomChannel do
  use Phoenix.Channel

  alias MyApp.Rooms
  alias MyApp.Accounts

  @impl true
  def join("room:" <> room_id, _params, socket) do
    # BUG: This channel process needs DB access via Rooms.get_room!/1, but
    # there is no Phoenix.Ecto.SQL.Sandbox.allow/3 call to grant the channel
    # process the sandbox allowance from the test process.
    case Rooms.get_room(room_id) do
      nil ->
        {:error, %{reason: "not_found"}}

      room ->
        {:ok, assign(socket, :room, room)}
    end
  end

  @impl true
  def handle_in("new_msg", %{"body" => body}, socket) do
    user = Accounts.get_user!(socket.assigns.user_id)
    {:ok, msg} = Rooms.create_message(socket.assigns.room, user, body)
    broadcast!(socket, "new_msg", %{body: msg.body, user_email: user.email})
    {:noreply, socket}
  end
end
