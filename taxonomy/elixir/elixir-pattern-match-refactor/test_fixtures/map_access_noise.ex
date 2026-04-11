# fixture: Non-assertive map access throughout. Should refactor to static map.key or
# function-head destructuring per the official anti-patterns guide.
defmodule MyApp.OrderFormatter do
  def summary(order) do
    id = order[:id]
    items = order[:items]
    total = order[:total]

    if id != nil && items != nil && total != nil do
      formatted_items =
        Enum.map(items, fn item ->
          name = item[:name]
          qty = item[:quantity]
          "#{qty}x #{name}"
        end)

      "Order #{id}: #{Enum.join(formatted_items, ", ")} — Total: $#{total}"
    else
      "Invalid order"
    end
  end

  def shipping_address(order) do
    user = order[:user]

    if user != nil do
      address = user[:address]

      if address != nil do
        street = address[:street]
        city = address[:city]
        zip = address[:zip]
        "#{street}, #{city} #{zip}"
      else
        "No address"
      end
    else
      "No user"
    end
  end

  def plot_point(point) do
    x = point[:x]
    y = point[:y]
    z = point[:z]
    {x, y, z}
  end
end
