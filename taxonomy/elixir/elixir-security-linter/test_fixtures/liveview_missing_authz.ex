# fixture: LiveView handle_event with no authorization check
# Vulnerability: delete/update events trust the parameter without ownership
# check. Classic Phoenix LiveView security failure.
defmodule MyAppWeb.PostLive.Index do
  use MyAppWeb, :live_view

  alias MyApp.Blog
  alias MyApp.Blog.Post
  alias MyApp.Repo

  @impl true
  def mount(_params, _session, socket) do
    {:ok, stream(socket, :posts, Blog.list_posts())}
  end

  @impl true
  def handle_event("delete", %{"id" => id}, socket) do
    post = Repo.get!(Post, id)
    {:ok, _} = Repo.delete(post)
    {:noreply, stream_delete(socket, :posts, post)}
  end

  @impl true
  def handle_event("publish", %{"id" => id}, socket) do
    post = Repo.get!(Post, id)
    {:ok, updated} = Blog.update_post(post, %{published: true})
    {:noreply, stream_insert(socket, :posts, updated)}
  end

  @impl true
  def handle_event("promote_to_admin", %{"user_id" => user_id}, socket) do
    if socket.assigns.current_user.role == "admin" do
      MyApp.Accounts.promote_user(user_id)
      {:noreply, put_flash(socket, :info, "User promoted")}
    else
      {:noreply, put_flash(socket, :error, "Denied")}
    end
  end
end
