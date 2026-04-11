# fixture: Imperative-style transform pipeline. Should rebuild around |> and Enum.
defmodule MyApp.ReportBuilder do
  def build(orders) do
    valid_orders = []

    for order <- orders do
      if order.status == "completed" do
        valid_orders = [order | valid_orders]
      end
    end

    total = 0

    for order <- valid_orders do
      line_total = order.quantity * order.price
      total = total + line_total
    end

    tax = total * 0.08
    grand_total = total + tax

    report = %{}
    report = Map.put(report, :subtotal, total)
    report = Map.put(report, :tax, tax)
    report = Map.put(report, :grand_total, grand_total)
    report = Map.put(report, :order_count, length(valid_orders))
    report
  end

  def format_lines(orders) do
    lines = []

    Enum.each(orders, fn order ->
      line = "#{order.id}: #{order.product} x#{order.quantity}"
      lines = lines ++ [line]
    end)

    result = Enum.join(lines, "\n")
    result
  end
end
