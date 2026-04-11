# fixture: LiveComponent with N+1 queries in update/2 — should use preload/1
defmodule MyAppWeb.UserDetailComponent do
  use MyAppWeb, :live_component

  alias MyApp.Accounts
  alias MyApp.Billing

  # ANTI-PATTERN: both queries run once per rendered component instance
  def update(%{user_id: user_id} = assigns, socket) do
    user = Accounts.get_user!(user_id)
    plan = Billing.get_plan_for_user(user_id)

    socket =
      socket
      |> assign(assigns)
      |> assign(:user, user)
      |> assign(:plan, plan)

    {:ok, socket}
  end

  def render(assigns) do
    ~H"""
    <div class="user-detail" id={@id}>
      <h3>{@user.name}</h3>
      <p>Plan: {@plan.name}</p>
      <p>Monthly: ${@plan.monthly_cents / 100}</p>
    </div>
    """
  end
end

defmodule MyAppWeb.UserListLive2 do
  use MyAppWeb, :live_view

  alias MyApp.Accounts

  def mount(_params, _session, socket) do
    user_ids = Accounts.list_user_ids()
    {:ok, assign(socket, :user_ids, user_ids)}
  end

  def render(assigns) do
    ~H"""
    <div>
      <%= for id <- @user_ids do %>
        <.live_component module={MyAppWeb.UserDetailComponent} id={"user-#{id}"} user_id={id} />
      <% end %>
    </div>
    """
  end
end
