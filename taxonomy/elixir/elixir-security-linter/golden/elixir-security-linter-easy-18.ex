# golden: liveview authorization fix — ownership + can? checks
defmodule MyAppWeb.PostLive.Index do
  use MyAppWeb, :live_view

  alias MyApp.Blog
  alias MyApp.Blog.Post
  alias MyApp.Accounts.Policy
  alias MyApp.Repo

  @impl true
  def mount(_params, _session, socket) do
    {:ok, stream(socket, :posts, Blog.list_posts())}
  end

  @impl true
  def handle_event("delete", %{"id" => id}, socket) do
    current_user = socket.assigns.current_user
    post = Blog.get_user_post!(current_user, id)

    if Policy.can?(current_user, :delete, post) do
      {:ok, _} = Blog.delete_post(current_user, post)
      {:noreply, stream_delete(socket, :posts, post)}
    else
      {:noreply, put_flash(socket, :error, "Not authorized")}
    end
  end

  @impl true
  def handle_event("publish", %{"id" => id}, socket) do
    current_user = socket.assigns.current_user
    post = Blog.get_user_post!(current_user, id)

    if Policy.can?(current_user, :publish, post) do
      {:ok, updated} = Blog.publish_post(current_user, post)
      {:noreply, stream_insert(socket, :posts, updated)}
    else
      {:noreply, put_flash(socket, :error, "Not authorized")}
    end
  end

  @impl true
  def handle_event("promote_to_admin", %{"user_id" => user_id}, socket) do
    current_user = socket.assigns.current_user

    if Policy.can?(current_user, :promote, :any) do
      MyApp.Accounts.promote_user(current_user, user_id)
      {:noreply, put_flash(socket, :info, "User promoted")}
    else
      {:noreply, put_flash(socket, :error, "Denied")}
    end
  end
end
