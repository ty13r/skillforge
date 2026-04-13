# AST Quality Analyzer — outputs JSON metrics for a given .ex file
# Usage: elixir ast_quality.exs <path_to_file.ex>

[file | _] = System.argv()
code = File.read!(file)
{:ok, ast} = Code.string_to_quoted(code, columns: true)

defmodule ASTCounter do
  def count(ast, code) do
    state = %{
      functions: 0, private_functions: 0, impl_annotations: 0,
      pipe_chains: 0, pattern_match_heads: 0, case_expressions: 0,
      if_expressions: 0, guard_clauses: 0, module_attributes: 0,
    }
    {_, state} = Macro.prewalk(ast, state, &walk/2)

    lines = code |> String.split("\n") |> length()
    non_empty = code |> String.split("\n") |> Enum.reject(&(String.trim(&1) == "")) |> length()

    # Template pattern counts
    heex_modern = length(Regex.scan(~r/\{[^}]+\}/, code))
    heex_legacy = length(Regex.scan(~r/<%=.*?%>/, code))
    for_dir = length(Regex.scan(~r/:for=/, code))
    if_dir = length(Regex.scan(~r/:if=/, code))
    for_leg = length(Regex.scan(~r/<%= for\b/, code))
    if_leg = length(Regex.scan(~r/<%= if\b/, code))

    total_fns = state.functions + state.private_functions
    %{
      functions: state.functions, private_functions: state.private_functions,
      impl_annotations: state.impl_annotations, pipe_chains: state.pipe_chains,
      pattern_match_heads: state.pattern_match_heads, guard_clauses: state.guard_clauses,
      module_attributes: state.module_attributes, case_expressions: state.case_expressions,
      if_expressions: state.if_expressions, total_lines: lines, non_empty_lines: non_empty,
      heex_modern: heex_modern, heex_legacy: heex_legacy,
      for_directive: for_dir, if_directive: if_dir, for_legacy: for_leg, if_legacy: if_leg,
      avg_fn_length: (if total_fns > 0, do: Float.round(non_empty / total_fns, 1), else: 0.0),
      impl_coverage: (if state.functions > 0, do: Float.round(min(state.impl_annotations / state.functions, 1.0), 2), else: 0.0),
      pipe_density: (if non_empty > 0, do: Float.round(state.pipe_chains / non_empty * 10, 2), else: 0.0),
      template_modernity: (if heex_modern + heex_legacy > 0, do: Float.round(heex_modern / (heex_modern + heex_legacy), 2), else: 1.0),
    }
  end

  defp walk({:def, _, [{:when, _, _} | _]} = node, state) do
    {node, %{state | functions: state.functions + 1, guard_clauses: state.guard_clauses + 1, pattern_match_heads: state.pattern_match_heads + 1}}
  end
  defp walk({:def, _, [{name, _, args} | _]} = node, state) when is_atom(name) do
    has_pat = case args do
      nil -> false
      a -> Enum.any?(a, &is_pat?/1)
    end
    s = %{state | functions: state.functions + 1}
    {node, if(has_pat, do: %{s | pattern_match_heads: s.pattern_match_heads + 1}, else: s)}
  end
  defp walk({:defp, _, _} = node, state), do: {node, %{state | private_functions: state.private_functions + 1}}
  defp walk({:@, _, [{:impl, _, _}]} = node, state), do: {node, %{state | impl_annotations: state.impl_annotations + 1}}
  defp walk({:@, _, [{n, _, _}]} = node, state) when n not in [:impl, :doc, :moduledoc, :behaviour, :derive, :type, :spec, :callback],
    do: {node, %{state | module_attributes: state.module_attributes + 1}}
  defp walk({:|>, _, _} = node, state), do: {node, %{state | pipe_chains: state.pipe_chains + 1}}
  defp walk({:case, _, _} = node, state), do: {node, %{state | case_expressions: state.case_expressions + 1}}
  defp walk({:if, _, _} = node, state), do: {node, %{state | if_expressions: state.if_expressions + 1}}
  defp walk(node, state), do: {node, state}

  defp is_pat?({:%, _, _}), do: true
  defp is_pat?({:%{}, _, _}), do: true
  defp is_pat?({:=, _, _}), do: true
  defp is_pat?(_), do: false
end

metrics = ASTCounter.count(ast, code)
# Output as parseable format (no Jason dependency)
pairs = Enum.map(metrics, fn {k, v} -> "\"#{k}\": #{inspect(v)}" end) |> Enum.join(", ")
IO.puts("{#{pairs}}")
