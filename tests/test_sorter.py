from boa_core.models import AuthorityItem, AuthorityCategory
from boa_core.sorter import sort_and_group_authorities, alphabetical_sort_key

def test_alphabetical_tie_breaker():
    items = [
        AuthorityItem(id="1", raw_citation="", title="Management Corporation Strata Title Plan No 1786 v Huang Hsiang Shui"),
        AuthorityItem(id="2", raw_citation="", title="Low Yung Chyuan v The MCST Plan No. 2178"),
        AuthorityItem(id="3", raw_citation="", title="Management Corporation Strata Title Plan No 1378 v Chen Ee Yueh Rachel"),
        AuthorityItem(id="4", raw_citation="", title="Management Corporation Strata Title Plan No 940 v Lim Florence Marjorie"),
        AuthorityItem(id="5", raw_citation="", title="The Management Corporation Strata Title Plan No. 3631 v Richard Koh"),
    ]
    
    # Sort them
    sorted_items = sorted(items, key=alphabetical_sort_key)
    titles = [i.title for i in sorted_items]
    
    print("Sorted items:")
    for t in titles:
        print("  -", t)
        
    # Low Yung Chyuan starts with 'l', so it comes first
    assert titles[0].startswith("Low Yung Chyuan")
    # MCST 1378 comes before MCST 1786, because '1378' < '1786'
    assert titles.index("Management Corporation Strata Title Plan No 1378 v Chen Ee Yueh Rachel") < \
           titles.index("Management Corporation Strata Title Plan No 1786 v Huang Hsiang Shui")


def test_grouping_and_reordering():
    item_sg_case = AuthorityItem(id="1", raw_citation="", title="Case A", category=AuthorityCategory.SINGAPORE_CASES)
    item_sg_stat = AuthorityItem(id="2", raw_citation="", title="Act B", category=AuthorityCategory.SINGAPORE_STATUTES)
    item_fc_case = AuthorityItem(id="3", raw_citation="", title="Foreign C", category=AuthorityCategory.FOREIGN_CASES)
    item_fc_stat = AuthorityItem(id="4", raw_citation="", title="Foreign D", category=AuthorityCategory.FOREIGN_STATUTES)
    
    # Default order: Singapore Cases, Singapore Statutes, Foreign Cases, Foreign Statutes
    grouped = sort_and_group_authorities([item_sg_case, item_sg_stat, item_fc_case, item_fc_stat])
    assert list(grouped.keys()) == [
        AuthorityCategory.SINGAPORE_CASES.value,
        AuthorityCategory.SINGAPORE_STATUTES.value,
        AuthorityCategory.FOREIGN_CASES.value,
        AuthorityCategory.FOREIGN_STATUTES.value
    ]
    
    # Custom order: Put Statutes first
    custom_order = [
        AuthorityCategory.SINGAPORE_STATUTES.value,
        AuthorityCategory.SINGAPORE_CASES.value,
        AuthorityCategory.FOREIGN_CASES.value,
    ]
    grouped_custom = sort_and_group_authorities(
        [item_sg_case, item_sg_stat, item_fc_case, item_fc_stat],
        custom_order=custom_order
    )
    assert list(grouped_custom.keys())[0] == AuthorityCategory.SINGAPORE_STATUTES.value
    
    # Merging Foreign Statutes into Foreign Cases
    grouped_merged = sort_and_group_authorities(
        [item_sg_case, item_sg_stat, item_fc_case, item_fc_stat],
        merged_groups={AuthorityCategory.FOREIGN_STATUTES.value: AuthorityCategory.FOREIGN_CASES.value}
    )
    assert AuthorityCategory.FOREIGN_STATUTES.value not in grouped_merged
    assert len(grouped_merged[AuthorityCategory.FOREIGN_CASES.value]) == 2


if __name__ == "__main__":
    test_alphabetical_tie_breaker()
    test_grouping_and_reordering()
    print("\nAll sorter tests passed successfully!")
