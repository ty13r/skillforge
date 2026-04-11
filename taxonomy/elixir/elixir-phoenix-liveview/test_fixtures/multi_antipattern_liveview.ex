# fixture: deliberately bad LiveView with 5+ distinct anti-patterns for detection challenges
defmodule MyAppWeb.ProjectsLive do
  use MyAppWeb, :live_view

  alias MyApp.Projects
  alias MyApp.Accounts

  # ANTI-PATTERN 1: DB query in mount/3
  # ANTI-PATTERN 2: PubSub subscribe without connected?/1
  # ANTI-PATTERN 3: large collection via assign, should be stream
  # ANTI-PATTERN 4: unscoped PubSub topic
  def mount(_params, %{"user_id" => user_id}, socket) do
    current_user = Accounts.get_user!(user_id)
    projects = Projects.list_all_projects() # 8000+ rows
    Phoenix.PubSub.subscribe(MyApp.PubSub, "projects")

    socket =
      socket
      |> assign(:current_user, current_user)
      |> assign(:projects, projects)

    {:ok, socket}
  end

  def render(assigns) do
    ~L"""
    <div>
      <h1>Projects</h1>
      <%= for p <- @projects do %>
        <div class="project">
          <%= live_link p.name, to: Routes.project_path(@socket, :show, p) %>
        </div>
      <% end %>
    </div>
    """
  end

  # ANTI-PATTERN 5: no authorization check — any user can archive any project
  def handle_event("archive", %{"id" => id}, socket) do
    project = Projects.get_project!(id)
    {:ok, _} = Projects.archive_project(project)
    Phoenix.PubSub.broadcast(MyApp.PubSub, "projects", {:archived, project})
    {:noreply, socket}
  end

  # ANTI-PATTERN 6: function head soup
  def handle_event(
        "update",
        %{"project" => %{"id" => id, "name" => name, "owner_id" => owner, "priority" => priority}} = _params,
        %{assigns: %{current_user: %{id: _user_id}}} = socket
      ) do
    Projects.update_project(id, %{name: name, owner_id: owner, priority: priority})
    {:noreply, socket}
  end

  def handle_info({:archived, _project}, socket) do
    projects = Projects.list_all_projects()
    {:noreply, assign(socket, :projects, projects)}
  end
end
