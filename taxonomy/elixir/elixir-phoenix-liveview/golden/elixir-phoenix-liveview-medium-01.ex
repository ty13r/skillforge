# golden: full 1.6 → 1.7 LiveView migration — ~p routes, <.link>, :for, :if, handle_params pattern
defmodule MyAppWeb.UserListLive do
  use MyAppWeb, :live_view

  alias MyApp.Accounts

  def mount(_params, _session, socket) do
    {:ok, socket}
  end

  def handle_params(_params, _url, socket) do
    {:noreply, assign(socket, :users, Accounts.list_users())}
  end

  def render(assigns) do
    ~H"""
    <div>
      <h1>Users</h1>
      <.link navigate={~p"/users/new"} class="btn">New user</.link>

      <ul>
        <li :for={user <- @users}>
          <.link navigate={~p"/users/#{user}"}>{user.name}</.link>
          <span :if={user.admin} class="badge">admin</span>
          <.link patch={~p"/users/#{user}/edit"}>edit</.link>
        </li>
      </ul>

      <.link patch={~p"/users"}>Reload</.link>
    </div>
    """
  end

  def handle_event("delete", %{"id" => id}, socket) do
    user = Accounts.get_user!(id)
    {:ok, _} = Accounts.delete_user(user)
    {:noreply, push_navigate(socket, to: ~p"/users")}
  end
end
