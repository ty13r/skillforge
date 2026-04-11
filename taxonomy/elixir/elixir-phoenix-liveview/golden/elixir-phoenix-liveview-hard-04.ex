# golden: LiveComponent N+1 fix with preload/1 batching
defmodule MyAppWeb.UserDetailComponent do
  use MyAppWeb, :live_component

  alias MyApp.Accounts
  alias MyApp.Billing

  def preload(list_of_assigns) do
    user_ids = Enum.map(list_of_assigns, & &1.user_id)
    users = Accounts.get_users(user_ids)
    plans = Billing.get_plans_for_users(user_ids)

    users_by_id = Map.new(users, &{&1.id, &1})
    plans_by_user = Map.new(plans, &{&1.user_id, &1})

    Enum.map(list_of_assigns, fn assigns ->
      assigns
      |> Map.put(:user, Map.fetch!(users_by_id, assigns.user_id))
      |> Map.put(:plan, Map.fetch!(plans_by_user, assigns.user_id))
    end)
  end

  def update(assigns, socket) do
    {:ok, assign(socket, assigns)}
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
