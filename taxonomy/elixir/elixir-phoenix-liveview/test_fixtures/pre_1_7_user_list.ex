# fixture: pre-1.7 LiveView using Routes.* helpers, live_patch/live_redirect, and <%= for %> loops
defmodule MyAppWeb.UserListLive do
  use MyAppWeb, :live_view

  alias MyApp.Accounts
  alias MyApp.Accounts.User

  def mount(_params, _session, socket) do
    users = Accounts.list_users()
    {:ok, assign(socket, users: users)}
  end

  def render(assigns) do
    ~L"""
    <div>
      <h1>Users</h1>
      <%= live_patch "New user", to: Routes.user_path(@socket, :new), class: "btn" %>

      <ul>
        <%= for user <- @users do %>
          <li>
            <%= live_redirect user.name, to: Routes.user_path(@socket, :show, user) %>
            <%= if user.admin do %>
              <span class="badge">admin</span>
            <% end %>
            <%= live_link "edit", to: Routes.user_path(@socket, :edit, user) %>
          </li>
        <% end %>
      </ul>

      <%= live_patch "Reload", to: Routes.user_path(@socket, :index) %>
    </div>
    """
  end

  def handle_event("delete", %{"id" => id}, socket) do
    user = Accounts.get_user!(id)
    {:ok, _} = Accounts.delete_user(user)
    {:noreply, push_redirect(socket, to: Routes.user_path(socket, :index))}
  end
end
