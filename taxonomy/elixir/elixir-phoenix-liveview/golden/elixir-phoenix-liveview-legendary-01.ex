# golden: multi-anti-pattern LiveView fully cleaned — DB moved to handle_params, scoped PubSub,
# stream for collection, connected?/1 guard, per-event auth, clean pattern match
defmodule MyAppWeb.ProjectsLive do
  use MyAppWeb, :live_view

  alias MyApp.Projects
  alias MyApp.Accounts

  on_mount {MyAppWeb.UserAuth, :ensure_authenticated}

  def mount(_params, %{"user_id" => user_id}, socket) do
    current_user = Accounts.get_user!(user_id)
    scope = %MyApp.Scope{user: current_user}
    topic = "projects:org:#{current_user.org_id}"

    if connected?(socket) do
      Phoenix.PubSub.subscribe(MyApp.PubSub, topic)
    end

    socket =
      socket
      |> assign(:current_user, current_user)
      |> assign(:scope, scope)
      |> assign(:topic, topic)
      |> stream(:projects, [])

    {:ok, socket}
  end

  def handle_params(_params, _url, socket) do
    projects = Projects.list_projects(socket.assigns.scope)
    {:noreply, stream(socket, :projects, projects, reset: true)}
  end

  def render(assigns) do
    ~H"""
    <div>
      <h1>Projects</h1>
      <div id="projects" phx-update="stream">
        <div :for={{dom_id, p} <- @streams.projects} id={dom_id} class="project">
          <.link navigate={~p"/projects/#{p}"}>{p.name}</.link>
        </div>
      </div>
    </div>
    """
  end

  def handle_event("archive", %{"id" => id}, socket) do
    project = Projects.get_project!(id)

    case authorize(socket.assigns.scope, project) do
      :ok ->
        {:ok, archived} = Projects.archive_project(project)
        Phoenix.PubSub.broadcast(MyApp.PubSub, socket.assigns.topic, {:archived, archived})
        {:noreply, stream_delete(socket, :projects, archived)}

      :error ->
        {:noreply, put_flash(socket, :error, "Not authorized")}
    end
  end

  def handle_event("update", %{"project" => params}, socket) do
    %{"id" => id} = params

    case authorize(socket.assigns.scope, Projects.get_project!(id)) do
      :ok ->
        {:ok, updated} = Projects.update_project(id, params)
        {:noreply, stream_insert(socket, :projects, updated)}

      :error ->
        {:noreply, put_flash(socket, :error, "Not authorized")}
    end
  end

  def handle_info({:archived, project}, socket) do
    {:noreply, stream_delete(socket, :projects, project)}
  end

  defp authorize(%{user: %{org_id: org_id}}, %{org_id: org_id}), do: :ok
  defp authorize(_scope, _project), do: :error
end
