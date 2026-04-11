# golden: stateless LiveComponent demoted to function component
defmodule MyAppWeb.UserCardComponent do
  use Phoenix.Component

  attr :id, :string, required: true
  attr :user, :map, required: true
  attr :badge, :string, default: nil
  attr :rest, :global

  def user_card(assigns) do
    ~H"""
    <div class="user-card" id={@id} {@rest}>
      <img src={@user.avatar_url} alt={@user.name} />
      <h4>{@user.name}</h4>
      <p>{@user.title}</p>
      <span :if={@badge} class="badge">{@badge}</span>
    </div>
    """
  end
end
