# fixture: a LiveComponent that has no state and no handle_event — should be a function component
defmodule MyAppWeb.UserCardComponent do
  use MyAppWeb, :live_component

  def mount(socket) do
    {:ok, socket}
  end

  def update(assigns, socket) do
    {:ok, assign(socket, assigns)}
  end

  def render(assigns) do
    ~H"""
    <div class="user-card" id={@id}>
      <img src={@user.avatar_url} alt={@user.name} />
      <h4>{@user.name}</h4>
      <p>{@user.title}</p>
      <%= if @badge do %>
        <span class="badge">{@badge}</span>
      <% end %>
    </div>
    """
  end
end

defmodule MyAppWeb.TeamLive do
  use MyAppWeb, :live_view

  alias MyApp.Teams

  def mount(_params, _session, socket) do
    {:ok, socket}
  end

  def handle_params(%{"team_id" => team_id}, _url, socket) do
    members = Teams.list_members(team_id)
    {:noreply, assign(socket, :members, members)}
  end

  def render(assigns) do
    ~H"""
    <div class="team">
      <%= for m <- @members do %>
        <.live_component
          module={MyAppWeb.UserCardComponent}
          id={"member-#{m.id}"}
          user={m}
          badge={m.title}
        />
      <% end %>
    </div>
    """
  end
end
