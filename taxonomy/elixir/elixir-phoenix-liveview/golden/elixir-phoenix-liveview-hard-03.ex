# golden: per-event authorization with Scope pattern — no UI-trust, re-check ownership server-side
defmodule MyAppWeb.PostsLive do
  use MyAppWeb, :live_view

  alias MyApp.Posts
  alias MyApp.Accounts

  on_mount {MyAppWeb.UserAuth, :ensure_authenticated}

  def mount(_params, %{"user_id" => user_id}, socket) do
    current_user = Accounts.get_user!(user_id)
    scope = %MyApp.Scope{user: current_user}

    socket =
      socket
      |> assign(:current_user, current_user)
      |> assign(:scope, scope)
      |> stream(:posts, [])

    {:ok, socket}
  end

  def handle_params(_params, _url, socket) do
    posts = Posts.list_posts(socket.assigns.scope)
    {:noreply, stream(socket, :posts, posts, reset: true)}
  end

  def render(assigns) do
    ~H"""
    <div id="posts" phx-update="stream">
      <div :for={{dom_id, post} <- @streams.posts} id={dom_id} class="post">
        <h3>{post.title}</h3>
        <p>{post.body}</p>
        <button
          :if={post.author_id == @current_user.id}
          phx-click="delete"
          phx-value-id={post.id}
        >
          Delete
        </button>
      </div>
    </div>
    """
  end

  def handle_event("delete", %{"id" => id}, socket) do
    post = Posts.get_post!(id)

    case authorize(socket.assigns.current_user, post) do
      :ok ->
        {:ok, _} = Posts.delete_post(post)
        {:noreply, stream_delete(socket, :posts, post)}

      :error ->
        {:noreply, put_flash(socket, :error, "Not authorized")}
    end
  end

  defp authorize(%{id: user_id}, %{author_id: user_id}), do: :ok
  defp authorize(_user, _post), do: :error
end
