# fixture: LiveView uses assign_async — test does not call render_async/1 and assertions fail silently
defmodule MyAppWeb.UserListLive do
  use MyAppWeb, :live_view

  alias MyApp.Accounts

  @impl true
  def mount(_params, _session, socket) do
    {:ok,
     socket
     |> assign(:page_title, "Users")
     |> assign_async(:users, fn ->
       {:ok, %{users: Accounts.list_users()}}
     end)}
  end

  @impl true
  def render(assigns) do
    ~H"""
    <div>
      <h1>{@page_title}</h1>

      <.async_result :let={users} assign={@users}>
        <:loading>Loading users...</:loading>
        <:failed>Failed to load users</:failed>
        <ul id="users">
          <li :for={user <- users} id={"user-#{user.id}"}>{user.email}</li>
        </ul>
      </.async_result>
    </div>
    """
  end
end
