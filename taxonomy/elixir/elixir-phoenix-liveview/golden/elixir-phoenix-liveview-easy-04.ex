# golden: ~p route interpolation with <.link navigate={...}>
defmodule MyAppWeb.ShowLinkLive do
  use MyAppWeb, :live_view

  def mount(_params, _session, socket) do
    {:ok, assign(socket, :user, %{id: 42})}
  end

  def render(assigns) do
    ~H"""
    <.link navigate={~p"/users/#{@user}"}>Profile</.link>
    """
  end
end
