# fixture: LiveView that trusts UI-level hiding for auth — handle_event has no authorization
defmodule MyAppWeb.PostsLive do
  use MyAppWeb, :live_view

  alias MyApp.Posts
  alias MyApp.Accounts

  def mount(_params, %{"user_id" => user_id}, socket) do
    current_user = Accounts.get_user!(user_id)
    posts = Posts.list_posts()
    {:ok, assign(socket, current_user: current_user, posts: posts)}
  end

  def render(assigns) do
    ~H"""
    <div>
      <%= for post <- @posts do %>
        <div class="post" id={"post-#{post.id}"}>
          <h3>{post.title}</h3>
          <p>{post.body}</p>
          <%= if post.author_id == @current_user.id do %>
            <button phx-click="delete" phx-value-id={post.id}>Delete</button>
          <% end %>
        </div>
      <% end %>
    </div>
    """
  end

  # ANTI-PATTERN: the UI hides the button but handle_event doesn't re-check ownership.
  # A savvy user can call the event directly via DevTools.
  def handle_event("delete", %{"id" => id}, socket) do
    post = Posts.get_post!(id)
    {:ok, _} = Posts.delete_post(post)
    posts = Enum.reject(socket.assigns.posts, &(&1.id == post.id))
    {:noreply, assign(socket, :posts, posts)}
  end
end
