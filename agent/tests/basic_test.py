from langchain.agents import create_agent
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from agent.src.agent import SYSTEM_PROMPT, build_maintenance_prompt


class BindableFakeChatModel(FakeListChatModel):
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self


def test_iceberg_polaris_maintenance_action() -> None:
    analysis_result = {
        "operation": "REWRITE_DATA_FILES",
        "reason": "The table contains a very high percentage of small files.",
        "priority": "HIGH",
        "confidence": 0.94,
    }
    expected_action = (
        "Run Iceberg compaction through the Polaris catalog: "
        "CALL polaris.system.rewrite_data_files("
        "table => 'analytics.events', "
        "strategy => 'binpack', "
        "options => map('target-file-size-bytes', '536870912')"
        "); "
        "schedule it during a low-write maintenance window, then validate that "
        "the table has fewer data files and healthier average file sizes."
    )

    model = BindableFakeChatModel(responses=[expected_action])
    agent = create_agent(
        model=model,
        tools=[],
        system_prompt=SYSTEM_PROMPT,
    )

    result = agent.invoke(
        {"messages": [{"role": "user", "content": build_maintenance_prompt(analysis_result)}]}
    )

    final_message = result["messages"][-1].content
    assert "CALL polaris.system.rewrite_data_files" in final_message
    assert "target-file-size-bytes" in final_message
    assert "maintenance window" in final_message
