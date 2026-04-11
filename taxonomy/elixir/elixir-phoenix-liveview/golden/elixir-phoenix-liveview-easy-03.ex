# golden: HEEx :if attribute replacing the legacy EEx conditional form
defmodule MyAppWeb.BadgeLive do
  use MyAppWeb, :live_view

  def mount(_params, _session, socket) do
    {:ok, assign(socket, :current_user, %{admin: true})}
  end

  def render(assigns) do
    ~H"""
    <span :if={@current_user.admin} class="badge">admin</span>
    """
  end
end
