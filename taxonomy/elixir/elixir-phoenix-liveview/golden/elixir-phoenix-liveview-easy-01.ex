# golden: rename Routes.user_path → ~p sigil in one call site
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
        </li>
      </ul>
    </div>
    """
  end
end
