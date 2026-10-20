/**
 * PAEON 체험 후 설문 — 구글 폼 자동 생성 스크립트 (v3, 16문항)
 * 사용법: script.google.com → 새 프로젝트 → 이 코드 전체 붙여넣기 → createPaeonSurvey 실행
 *         → 권한 승인 → 아래 "실행 로그"에 편집·응답용 링크가 나온다.
 * 구성: 1번 연령대 / 2~6번 사용 경험 / 7~8번 추천 의향(NPS) / 9번 계속 사용 의향(낮은 답은 10~11번으로 분기) / 12~16번 개선·가격
 * 이미 만든 폼이 있으면 다시 실행하지 말고 새 폼이 필요할 때만 실행한다(실행할 때마다 폼이 새로 생긴다).
 */
function createPaeonSurvey() {
  var form = FormApp.create('PAEON 체험 후 설문 (약 3분)');
  form.setDescription('체험해 주셔서 감사합니다. 정답은 없어요, 솔직한 느낌을 알려주세요!');
  form.setCollectEmail(false);
  form.setLimitOneResponsePerUser(false);
  form.setConfirmationMessage('응답이 기록됐어요!');

  // 섹션 1. 시작
  form.addMultipleChoiceItem()
    .setTitle('1. 연령대를 알려주세요.')
    .setChoiceValues(['10대', '20대', '30대', '40대', '50대', '60대 이상'])
    .setRequired(true);

  // 섹션 2. 사용 경험
  form.addPageBreakItem().setTitle('사용 경험');
  form.addCheckboxItem()
    .setTitle('2. 어디까지 해보셨나요?')
    .setChoiceValues([
      '가입',
      '건강정보 입력',
      '결과 확인',
      '챌린지 시작 (미션 고르기)',
      '오늘 미션 기록하기'
    ])
    .setRequired(true);
  form.addTextItem()
    .setTitle('3. 이 서비스가 어떤 도움을 준다고 설명하시겠어요?')
    .setRequired(true);
  form.addMultipleChoiceItem()
    .setTitle('4. 결과 화면에서 "양호"라는 표시를 봤다면, 어떤 뜻이라고 이해하셨나요?')
    .setChoiceValues([
      '건강에 문제가 없다는 뜻이에요',
      '지금 입력한 정보 기준으로 위험이 낮게 나왔다는 뜻이고, 건강을 보장하는 건 아니에요',
      '잘 모르겠어요',
      '"양호"가 나오지 않았거나 결과 화면을 보지 않았어요'
    ])
    .setRequired(true);
  form.addCheckboxItem()
    .setTitle('5. 사용 중 막히거나 헷갈린다고 느낀 적이 있었나요? (해당하는 항목을 모두 골라주세요)')
    .setChoiceValues([
      '가입·로그인',
      '대상 확인 (나이·병력 질문)',
      '건강정보 입력',
      '생활습관 설문',
      '결과 화면',
      '챌린지 미션 고르기',
      '미션 기록',
      '4주 재입력',
      '없었어요'
    ])
    .showOtherOption(true);
  form.addMultipleChoiceItem()
    .setTitle('6. 서비스를 쓰면서 화면이 늦게 뜨거나 버벅인다고 느낀 적이 있나요?')
    .setChoiceValues([
      '전혀 없었어요',
      '한두 번 있었지만 불편하지 않았어요',
      '여러 번 있어서 불편했어요',
      '너무 느려서 쓰기 어려웠어요'
    ])
    .setRequired(true);

  // 섹션 3. 추천 의향(NPS) + 계속 사용 의향 (분기)
  form.addPageBreakItem().setTitle('추천과 계속 사용 의향');
  form.addScaleItem()
    .setTitle('7. 이 서비스를 비슷한 고민을 가진 지인에게 추천할 의향이 얼마나 되나요?')
    .setBounds(0, 10)
    .setLabels('전혀 추천하지 않아요', '꼭 추천해요')
    .setRequired(true);
  form.addTextItem().setTitle('8. 그렇게 답하신 이유를 한 줄로 적어주세요. (선택)');
  var q6 = form.addMultipleChoiceItem()
    .setTitle('9. 이 서비스를 앞으로도 계속 쓰고 싶으신가요? 솔직하게 말씀해주시면 큰 도움이 돼요!' )
    .setRequired(true);

  // 섹션 4. 이유 (낮게 답한 사람만)
  var pageWhy = form.addPageBreakItem().setTitle('이유를 알려주세요');
  form.addMultipleChoiceItem()
    .setTitle('10. 계속 쓰기 어려운 가장 큰 이유는 무엇인가요?')
    .setChoiceValues([
      '건강 관리에 관심이 없어요',
      '웹 서비스 사용이 불편해요',
      '분석 결과를 신뢰하기 어려워요',
      '챌린지로 생활습관이 개선될지 모르겠어요'
    ])
    .showOtherOption(true)
    .setRequired(true);
  form.addParagraphTextItem().setTitle('11. 좀 더 자세히 알려주실 수 있나요? (선택)');

  // 섹션 5. 개선과 가격
  var pageNext = form.addPageBreakItem().setTitle('개선과 가격');
  form.addCheckboxItem()
    .setTitle('12. 만약 계속 사용한다면 가장 큰 이유는?')
    .setChoiceValues([
      '현재 건강 정보 확인 (고혈압 위험 정도·혈관 나이 추정)',
      '챌린지 미션 달성과 보상 획득',
      '챌린지 전/후 건강 상태 변화 확인',
      '장기적인 생활습관 기록 및 보관',
      '해당 없음'
    ])
    .showOtherOption(true)
    .setValidation(
      FormApp.createCheckboxValidation()
      .requireSelectAtMost(2)
      .setHelpText('최대 2개까지 고를 수 있어요.')
      .build()
  );
  form.addCheckboxItem()
    .setTitle('13. 더 좋은 서비스를 위해 가장 필요한 것은? (2개 선택)')
    .setChoiceValues(['더 다양한 챌린지', '보상 (포인트, 쿠폰 등)', '나의 건강 상태와 위험도에 대한 더 자세한 설명', '나에게 챌린지가 추천된 이유에 대한 설명','건강 상태와 생활습관 변화의 비교·확인', '더 간편하고 직관적인 사용 방식'])
    .showOtherOption(true)
    .setRequired(true)
    .setValidation(
      FormApp.createCheckboxValidation()
      .requireSelectExactly(2)
      .setHelpText('2개를 골라주세요.')
      .build()
  );
  form.addMultipleChoiceItem()
    .setTitle('14. 한 달 구독료가 얼마까지면 계속 쓰실 것 같나요?')
    .setHelpText('한 달에 낼 수 있는 최대 금액이 속한 구간을 골라주세요.')
    .setChoiceValues([
      '무료일 때만 쓸 것 같아요',
      '5,000원 미만',
      '5,000원 이상 ~ 10,000원 미만',
      '10,000원 이상 ~ 15,000원 미만',
      '15,000원 이상'
    ])
    .setRequired(true);
  form.addMultipleChoiceItem()
    .setTitle('15. 무료라면 건강 업체 제휴 광고가 나와도 괜찮으신가요?')
    .setChoiceValues(['괜찮아요', '상황에 따라 괜찮아요', '불편해요']);
  form.addParagraphTextItem().setTitle('16. 하고 싶은 말이 있다면 적어주세요. (선택)');

  // 9번 분기: 낮게 답하면 섹션 4(이유), 나머지는 섹션 5로 건너뜀
  q6.setChoices([
    q6.createChoice('매우 그렇다', pageNext),
    q6.createChoice('그렇다', pageNext),
    q6.createChoice('보통이다', pageNext),
    q6.createChoice('그렇지 않다', pageWhy),
    q6.createChoice('전혀 그렇지 않다', pageWhy)
  ]);
  Logger.log('편집 링크: ' + form.getEditUrl());
  Logger.log('응답용 링크(지인에게 보낼 링크): ' + form.getPublishedUrl());
}
