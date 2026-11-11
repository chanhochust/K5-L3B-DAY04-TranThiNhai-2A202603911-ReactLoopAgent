# Ghi chú phân tích · Day 04

Họ và tên: Trần Thị Nhài
MSSV: 2A202603911

## 1. Case được chọn

- ID case: **H1**. Câu hỏi yêu cầu đọc incident GitHub `h02n9572mx9y`, đi theo liên kết trong incident để tìm nguyên nhân, rồi so với incident Cloudflare `yaa0witbl2me`.
- Câu trả lời của agent: phần trạng thái, component và kết luận "không có bằng chứng chung nguyên nhân" đều ổn. Nhưng agent chỉ chép lại link sang `xr3myzj7ms51` mà không mở ra đọc, nên không nói được nguyên nhân phía GitHub. Ngoài ra agent lấy `updated_at` làm giờ kết thúc và không nhắc dữ liệu có thể bị cắt.
- Điểm ở lần chạy 1: **60/100**. Judge cho 85 nhưng bị giới hạn xuống 60 vì vi phạm `min_tool_steps: 2`.

## 2. Bằng chứng trong trace

```text
step 1  get_incident_details(github, h02n9572mx9y) + get_incident_details(cloudflare, yaa0witbl2me)
        update cuối của h02n...: "Please refer to the combined summary in this related incident:
        https://www.githubstatus.com/incidents/xr3myzj7ms51"
step 2  finish: stop  → trả lời luôn, không gọi get_incident_details(xr3myzj7ms51)
mechanical: tool_steps = 1 → score_cap = 60
```

Mình nghĩ lỗi nằm ở prompt và cách model ra quyết định, không phải ở vòng lặp hay dữ liệu: tool đã trả về đủ ID để đọc tiếp. Model gọi song song hai incident có sẵn trong câu hỏi, thấy đủ hai kết quả thì coi như xong, còn link trong update chỉ được xem là thông tin để trích dẫn. System prompt lúc đó cũng không có quy tắc nào bảo phải đọc tiếp incident liên quan.

H6 bị đúng lỗi này (cũng 60 vì chỉ có 1 step gọi tool). Trong khi đó A6 lại có đọc `xr3myzj7ms51`, nên model làm được việc này, chỉ là không nhất quán.

## 3. Thay đổi đã thực hiện

- Sửa gì, ở đâu (chỉ trong `agent.py`, kèm một file test mới):
  1. **System prompt**: thêm quy tắc "nếu update trỏ tới incident khác thì gọi `get_incident_details` cho ID đó ở lượt sau, rồi mới kết luận; nhớ trích URL".
  2. **Kiểm tra incident liên kết bằng code**: sau mỗi lần đọc incident thành công, agent tìm link `/incidents/<id>` trong các update. Nếu model định trả lời mà vẫn còn incident liên kết chưa đọc, agent ghi `validation_unread_related` vào trace và nhắc model đọc tiếp. Chỉ nhắc một lần, và chỉ khi còn đủ step, để không biến một run đang ổn thành `max_steps`.
  3. **Kiểm tra nguồn** (yêu cầu bắt buộc của Bài 4): nếu đã đọc incident thành công mà câu trả lời không có URL nào của incident đó thì ghi `validation_missing_source` và yêu cầu model sửa. Hết lượt mà vẫn thiếu thì trả `max_steps` chứ không báo `completed`.
  4. Thêm `tests/test_related_incident.py` cho bước kiểm tra ở mục 2. Toàn bộ 42 test đều pass.
- Vì sao chọn thay đổi này:

  Lỗi này nhìn thấy rõ trong trace và đo được bằng code (`min_tool_steps`), không phụ thuộc vào cảm nhận của judge. Ban đầu mình chỉ sửa prompt, rồi chạy thử riêng H1 và H6:

  | Phiên bản | H1 | H6 |
  |---|---|---|
  | Before | 60 (1 step gọi tool) | 60 (1 step gọi tool) |
  | Chỉ sửa prompt | 60, vẫn không đọc `xr3...` | **80**, đã đọc `xr3...` và nêu được nguyên nhân |
  | Thêm kiểm tra bằng code | **75**, được nhắc rồi đọc `xr3...`, nêu được nguyên nhân | không chạy lại |

  Prompt sửa được H6 nhưng không sửa được H1, vì prompt chỉ là lời khuyên. Nên mình thêm kiểm tra bằng code, theo đúng kiểu "phát hiện → ghi trace → bắt model làm tiếp" mà GUIDE gợi ý cho kiểm tra nguồn. Bước này chỉ chạy khi dữ liệu thật có link tới incident chưa đọc, và làm agent đọc thật incident đó, nên không phải là lách điểm.

  H1 lần này vẫn còn thiếu: trả lời bằng tiếng Anh, chưa nhắc dữ liệu có thể bị cắt. Hai điểm này không thuộc lỗi đã chọn nên mình không sửa tiếp, để tránh chỉnh theo từng case.

- Đánh đổi: agent sẽ đọc thêm incident liên kết kể cả khi người dùng không hỏi tới, tốn thêm khoảng một lượt gọi model. Nếu model phớt lờ lời nhắc thì lỗi vẫn còn. Kiểm tra nguồn chỉ đảm bảo có ít nhất một URL, không chứng minh mọi ý trong câu trả lời đều có nguồn.

## 4. So sánh hai lần chạy

| Chỉ số | `eval_before.json` | `eval_after.json` |
|---|---|---|
| Điểm tổng | 79.68 | 80.91 |
| Điểm case đã chọn | H1: 60 (judge 85, bị giới hạn) | H1: 75 (không còn vi phạm) |
| Số model calls | 55 | 53 |
| Token, chi phí nếu có | Agent khoảng 51.7k token ($0.012), judge khoảng 49.2k token ($0.009) | Agent khoảng 50.0k token ($0.011), judge khoảng 40.3k token ($0.007) |

Hai lần chạy cùng cấu hình: OpenRouter, `openai/gpt-4o-mini` cho cả agent và judge, `max_steps = 8`, cùng snapshot và 22 case.

- Lỗi đã giải quyết:
  - **H1** (60 → 75): trace có `validation_unread_related` ở step 2, sau đó agent đọc `xr3myzj7ms51` ở step 3 và nêu được nguyên nhân phía GitHub. Hết vi phạm `min_tool_steps`.
  - **H6** (60 → 75): lần này agent tự đọc `xr3myzj7ms51` ở step 2 nhờ quy tắc mới trong prompt, không cần lời nhắc.
  - Lời nhắc chỉ phải dùng ở H1. Kiểm tra nguồn không bị kích hoạt lần nào: các câu trả lời có đọc incident đều tự trích URL.
- Lỗi còn lại hoặc mới xuất hiện:
  - **H2** (100 → 50): lần này agent chỉ gọi `get_incident_details` mà không gọi `get_status`, nên bị giới hạn vì thiếu tool bắt buộc, dù judge vẫn cho đủ 100. Nhìn rộng hơn, số lần gọi tool giảm từ 58 xuống 43 (E1, A2, H5, A5 cũng gọi ít tool hơn). Mình chưa chắc đây là tác dụng phụ của prompt mới hay chỉ là dao động, vì mỗi phiên bản mới chạy một lần.
  - **A5** (40 → 45): vẫn nói "không có sự cố nào trong năm 2025", tức vẫn khẳng định quá mức từ dữ liệu chỉ có 50 incident gần nhất.
  - **E4** (100 → 75): liệt kê thêm Code Scanning và Copilot coding agent là component bị ảnh hưởng. Hai mục này có trong nội dung update nhưng không có trong trường `components`.
  - H1 vẫn chưa nhắc dữ liệu có thể bị cắt.
  - Các case không liên quan đến thay đổi cũng lên xuống khá nhiều (E1 +30, H7 +25, H4 +20, E6 −10, H8 −10), nên mức tăng 1.23 điểm tổng không đủ để kết luận agent tốt hơn hẳn. Điều chắc chắn hơn là H1 và H6 đã hết vi phạm kiểm tra bằng code.

## 5. Giới hạn

- **Điểm judge không ổn định và có lúc sai.** Judge cũng là gpt-4o-mini, tức model tự chấm bài của chính nó. Ở lần before, E1 bị trừ điểm vì ngày 05/11 dù `expected` ghi đúng ngày đó. H4 bị cho evidence = 0 với bài thơ, dù hướng dẫn chấm nói không trừ khi câu hỏi không cần tool. Ở H1, judge nói câu trả lời không thừa nhận thiếu bằng chứng chung, trong khi câu trả lời có nói rõ. Vì vậy mình đối chiếu với `expected` và trace, và tin vào các vi phạm kiểm tra bằng code hơn là điểm judge.
- **Snapshot cố định.** Dữ liệu chụp ngày 09/11/2026 và chỉ có 50 incident gần nhất mỗi provider, nên kết quả không nói gì về trạng thái thật hiện tại, và agent không thể trả lời đầy đủ các câu hỏi về khoảng thời gian dài (A5, H8).
- **Mỗi phiên bản chỉ chạy một lần.** Nhiều case không bị thay đổi vẫn lệch 10–30 điểm giữa hai lần chạy, nên không thể nói chắc thay đổi nào gây ra mức tăng hay giảm, trừ những case có bằng chứng rõ trong trace như H1 và H6. Muốn kết luận chắc hơn phải chạy nhiều lần và lấy trung bình.
- **Giới hạn của cải tiến.** Kiểm tra nguồn chỉ yêu cầu có ít nhất một URL. Kiểm tra incident liên kết chỉ nhắc một lần và chỉ nhận ra link dạng `/incidents/<id>`.
